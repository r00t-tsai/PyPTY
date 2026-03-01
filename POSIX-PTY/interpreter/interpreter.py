import os
import sys
import time
import shlex
import termios
import tty
import threading
import select

from session.session import Session

_default_shell = os.environ.get("SHELL", "bash")


_help = """Commands:
  !help                  Show this message
  !shell <exe>           Launch a new shell (e.g. !shell zsh)
  !resize <cols> <rows>  Resize the terminal
  !restart               Restart the root shell
  exit                   Exit current shell, or close if at root
"""

subshell = {
    "python", "python3",
    "bash", "zsh", "sh", "fish", "dash",
    "ftp", "sftp", "telnet",
    "sqlite3",
    "irb",
    "node",
    "gdb", "lldb",
}

_CTRL_C = b"\x03"
_CTRL_D = b"\x04"
_CTRL_Z = b"\x1a"
_CTRL_L = b"\x0c"

_PASSTHROUGH = {0x03, 0x04, 0x1a, 0x0c}


class _termiosttyrdr:

    def __init__(self, fd: int = sys.stdin.fileno()):
        self._fd         = fd
        self._old_attrs  = None
        self._buf: list[str] = []
        self.line_queue:  list[str]   = []
        self.ctrl_queue:  list[bytes] = []
        self._lock   = threading.Lock()
        self._event  = threading.Event()
        self._stop   = threading.Event()
        self._thread = threading.Thread(
            target=self.read, daemon=True, name="termiosttyrdr"
        )

    def start(self):
        self._old_attrs = termios.tcgetattr(self._fd)
        tty.setraw(self._fd)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._old_attrs is not None:
            try:
                termios.tcsetattr(self._fd, termios.TCSADRAIN, self._old_attrs)
            except termios.error:
                pass

    def read(self):
        while not self._stop.is_set():
            ready, _, _ = select.select([self._fd], [], [], 0.05)
            if not ready:
                continue

            try:
                ch = os.read(self._fd, 1)
            except OSError:
                break

            if not ch:
                break

            b = ch[0]

            if b in _PASSTHROUGH:
                with self._lock:
                    self.ctrl_queue.append(ch)
                self._event.set()

            elif b in (0x0D, 0x0A):
                line = "".join(self._buf)
                self._buf.clear()
                sys.stdout.write("\r\n")
                sys.stdout.flush()
                with self._lock:
                    self.line_queue.append(line)
                self._event.set()

            elif b == 0x7F or b == 0x08:
                if self._buf:
                    self._buf.pop()
                    sys.stdout.write("\x08 \x08")
                    sys.stdout.flush()

            elif b == 0x1B:
                select.select([self._fd], [], [], 0.02)
                try:
                    os.read(self._fd, 8)
                except OSError:
                    pass

            else:
                self._buf.append(ch.decode("utf-8", errors="replace"))
                sys.stdout.write(ch.decode("utf-8", errors="replace"))
                sys.stdout.flush()

    def inpwait(self, timeout: float = 0.05) -> bool:
        return self._event.wait(timeout)

    def drain(self) -> tuple[list[str], list[bytes]]:
        with self._lock:
            lines = self.line_queue[:]
            ctrls = self.ctrl_queue[:]
            self.line_queue.clear()
            self.ctrl_queue.clear()
            if not self.line_queue and not self.ctrl_queue:
                self._event.clear()
        return lines, ctrls


class Shell:

    def __init__(
        self,
        shell:    str | None = None,
        cols:     int = 120,
        rows:     int = 30,
        encoding: str = "utf-8",
    ):
        shell = shell or _default_shell
        self._root_shell = shell
        self._cols       = cols
        self._rows       = rows
        self._encoding   = encoding
        self._running    = False
        self._stack: list[tuple[str, Session, bool]] = []
        self._reader     = _termiosttyrdr()

    @property
    def _session(self) -> Session | None:
        return self._stack[-1][1] if self._stack else None

    @property
    def _depth(self) -> int:
        return len(self._stack)

    def _run(self):
        self._push_session(self._root_shell)
        self._running = True
        self._reader.start()

        try:
            while self._running:
                self._reader.inpwait(timeout=0.05)
                lines, ctrls = self._reader.drain()

                for ctrl in ctrls:
                    if ctrl == _CTRL_C:
                        self._ctrl_c()
                    elif ctrl == _CTRL_D:
                        self._ctrl_d()
                    elif ctrl in (_CTRL_Z, _CTRL_L):
                        if self._session:
                            self._session.send_raw(ctrl)

                for line in lines:
                    line = line.strip()
                    if not line:
                        continue
                    self._dispatch(line)

        finally:
            self._reader.stop()

    def _dispatch(self, line: str):
        if line in ("!help", "help"):
            print(_help)

        elif line.startswith("!shell"):
            parts = shlex.split(line)
            if len(parts) < 2:
                print("Usage: !shell <executable>")
            else:
                self._push_session(parts[1])

        elif line.startswith("!resize"):
            parts = shlex.split(line)
            if len(parts) != 3:
                print("Usage: !resize <cols> <rows>")
            else:
                try:
                    cols, rows = int(parts[1]), int(parts[2])
                    self._cols, self._rows = cols, rows
                    if self._session:
                        self._session.resize(cols, rows)
                except ValueError:
                    print("Error: cols and rows must be integers.")

        elif line == "!restart":
            self.cleanup()
            self._stack.clear()
            self._push_session(self._root_shell)

        elif line == "exit":
            if self._depth > 1:
                self._session.send_command("exit")
                time.sleep(0.3)
                self._pop()
            else:
                self._session.send_command("exit")
                time.sleep(0.3)
                self._running = False

        else:
            try:
                cmd_name = shlex.split(line)[0].lower()
                cmd_name = cmd_name.split("/")[-1]
            except ValueError:
                cmd_name = ""

            if cmd_name in subshell:
                self._session.send_command(line)
                time.sleep(0.5)
                self._push_tracker(cmd_name)
            else:
                self._session.send_command(line)
                time.sleep(0.2)

    def _ctrl_c(self):
        if self._session:
            self._session.send_urgent(_CTRL_C)

    def _ctrl_d(self):
        if self._session:
            self._session.send_urgent(_CTRL_D)

    def cleanup(self):
        while self._stack:
            self._pop(silent=True)

    def _push_session(self, shell: str):
        session = Session(shell, self._cols, self._rows, self._encoding)
        session.start()
        time.sleep(0.3)
        self._stack.append((shell, session, True))

    def _push_tracker(self, label: str):
        if not self._stack:
            return
        current_session = self._stack[-1][1]
        self._stack.append((label, current_session, False))

    def _pop(self, silent: bool = False):
        if not self._stack:
            return
        label, session, is_owner = self._stack.pop()
        if is_owner:
            session.stop()

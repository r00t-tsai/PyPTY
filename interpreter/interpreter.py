import time
import shlex
import msvcrt
import sys
import ctypes
import ctypes.wintypes as wintypes
import threading

from session.session import Session


kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

ENABLE_PROCESSED_INPUT = 0x0001
ENABLE_LINE_INPUT      = 0x0002
ENABLE_ECHO_INPUT      = 0x0004
STD_INPUT_HANDLE       = wintypes.DWORD(-10)


def _get_stdin_handle():
    return kernel32.GetStdHandle(STD_INPUT_HANDLE)

def _get_console_mode(handle) -> int:
    mode = wintypes.DWORD(0)
    kernel32.GetConsoleMode(handle, ctypes.byref(mode))
    return mode.value

def _set_console_mode(handle, mode: int):
    kernel32.SetConsoleMode(handle, wintypes.DWORD(mode))


_help = """Commands:
  !help                  Show this message
  !shell <exe>           Launch a new shell (e.g. !shell powershell.exe)
  !resize <cols> <rows>  Resize the terminal
  !restart               Restart the root shell
  exit                   Exit current shell or close if root
"""

subshell = {
    "diskpart",
    "powershell", "powershell.exe",
    "pwsh", "pwsh.exe",
    "python", "python3",
    "cmd", "cmd.exe",
    "wsl", "bash", "bash.exe",
    "ftp", "telnet", "sftp",
}

_CTRL_C = b"\x03"
_CTRL_Z = b"\x1a"


class _msvcrtrdr:

    _pass = {0x03, 0x1a, 0x1b}

    def __init__(self):
        self.line_queue: list[str]   = []
        self.ctrl_queue: list[bytes] = []
        self._buf    = []
        self._lock   = threading.Lock()
        self._event  = threading.Event()
        self._stop   = threading.Event()
        self._handle = None
        self._old_mode: int | None = None
        self._thread = threading.Thread(
            target=self.read, daemon=True, name="msvcrtrdr"
        )

    def start(self):
        self._handle   = _get_stdin_handle()
        self._old_mode = _get_console_mode(self._handle)
        raw_mode = self._old_mode & ~(
            ENABLE_PROCESSED_INPUT |
            ENABLE_LINE_INPUT      |
            ENABLE_ECHO_INPUT
        )
        _set_console_mode(self._handle, raw_mode)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._handle is not None and self._old_mode is not None:
            _set_console_mode(self._handle, self._old_mode)

    def _echo(self, text: str):
        sys.stdout.write(text)
        sys.stdout.flush()

    def read(self):
        while not self._stop.is_set():
            if not msvcrt.kbhit():
                time.sleep(0.01)
                continue
            ch = msvcrt.getwch()
            b  = ord(ch)

            if b in self._pass:
                with self._lock:
                    self.ctrl_queue.append(bytes([b]))
                self._event.set()

            elif b in (0x0D, 0x0A):
                line = "".join(self._buf)
                self._buf.clear()
                self._echo("\r\n")
                with self._lock:
                    self.line_queue.append(line)
                self._event.set()

            elif b == 0x08 or b == 0x7F:
                if self._buf:
                    self._buf.pop()
                    self._echo("\x08 \x08")

            else:
                self._buf.append(ch)
                self._echo(ch)

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
        shell:    str = "cmd.exe",
        cols:     int = 120,
        rows:     int = 30,
        encoding: str = "utf-8",
    ):
        self._root_shell = shell
        self._cols       = cols
        self._rows       = rows
        self._encoding   = encoding
        self._running    = False
        self._stack: list[tuple[str, Session, bool]] = []
        self.reader = _msvcrtrdr()

    @property
    def _session(self) -> Session | None:
        return self._stack[-1][1] if self._stack else None

    @property
    def _depth(self) -> int:
        return len(self._stack)

    def _run(self):
        self._p_session(self._root_shell)
        self._running = True
        self.reader.start()

        try:
            while self._running:
                self.reader.inpwait(timeout=0.05)
                lines, ctrls = self.reader.drain()

                for ctrl in ctrls:
                    if ctrl == _CTRL_C:
                        self._send_ctrl_c()
                    elif ctrl == _CTRL_Z:
                        if self._session:
                            self._session.send_urgent(_CTRL_Z)

                for line in lines:
                    line = line.strip()
                    if not line:
                        continue
                    self._dispatch(line)
        finally:
            self.reader.stop()

    def _dispatch(self, line: str):
        if line in ("!help", "help"):
            print(_help)

        elif line.startswith("!shell"):
            parts = shlex.split(line)
            if len(parts) < 2:
                print("Usage: !shell <executable>")
            else:
                self._p_session(parts[1])

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
            self._p_session(self._root_shell)

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
            except ValueError:
                cmd_name = ""

            if cmd_name in subshell:
                self._session.send_command(line)
                time.sleep(0.5)
                self._p_tracker(cmd_name)
            else:
                self._session.send_command(line)
                time.sleep(0.2)

    def _send_ctrl_c(self):
        if self._session:
            self._session.send_urgent(_CTRL_C)

    def cleanup(self):
        while self._stack:
            self._pop(silent=True)

    def _p_session(self, shell: str):
        session = Session(shell, self._cols, self._rows, self._encoding)
        session.start()
        time.sleep(0.3)
        self._stack.append((shell, session, True))

    def _p_tracker(self, label: str):
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

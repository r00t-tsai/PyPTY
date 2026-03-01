import time
import shlex
import msvcrt
import threading

from session.session import Session


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
_CTRL_Z = b"\x03"
_CR = b"\r\n"

class msvcrtrdr:
  _pass = {0x03, 0x1a, 0x1b}
  def __init__(self):
    self.l_queue: list[str] = []
    self.ctrl_queue: list[bytes] = []
    self._buf = []
    self._lock  = threading.Lock()
    self._event = threading.Event()
    self._stop  = threading.Event()
    self._thread = threading.Thread(
        target=self._read_loop, daemon=True, name="msvcrtrdr"
    )
    
  def start(self):
      self._thread.start()

  def stop(self):
      self._stop.set()


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

    @property
    def _session(self):
        return self._stack[-1][1] if self._stack else None

    @property
    def _depth(self) -> int:
        return len(self._stack)

    def _run(self):
        self._p_session(self._root_shell)
        self._running = True

        while self._running:
            try:
                line = input("")
            except EOFError:
                break

            line = line.strip()
            if not line:
                continue

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

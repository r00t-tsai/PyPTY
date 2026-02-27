import os
import time
import shlex

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


    @property
    def _session(self) -> Session | None:
        return self._stack[-1][1] if self._stack else None

    @property
    def _depth(self) -> int:
        return len(self._stack)

    def _run(self):
        self._push_session(self._root_shell)
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
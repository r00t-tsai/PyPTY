import time
from core.pty_console   import PTYConsole
from process.process    import spawn, ChildProcess
from iobridge.io_bridge import IOBridge


class Session:

    def __init__(
        self,
        shell:    str = "bash",
        cols:     int = 120,
        rows:     int = 30,
        encoding: str = "utf-8",
    ):
        self._shell    = shell
        self._cols     = cols
        self._rows     = rows
        self._encoding = encoding
        self._pty:     PTYConsole  | None = None
        self._process: ChildProcess | None = None
        self._bridge:  IOBridge    | None = None

    def start(self):
        self._pty     = PTYConsole(self._cols, self._rows)
        self._process = spawn(self._shell, self._pty.slave_fd)
        self._bridge  = IOBridge(self._pty.master_fd, self._encoding)
        self._bridge.start()

    def stop(self):
        if self._bridge:
            self._bridge.stop()
        if self._process:
            try:
                self._process.terminate()
            except Exception:
                pass
        if self._pty:
            self._pty.close()

    def send_command(self, command: str, delay: float = 0.05):
        if self._bridge:
            self._bridge.send_line(command, self._encoding)
            time.sleep(delay)

    def send_raw(self, data: bytes):
        if self._bridge:
            self._bridge.send(data)

    def resize(self, cols: int, rows: int):
        if self._pty:
            self._pty.resize(cols, rows)

    @property
    def pid(self) -> int | None:
        return self._process.pid if self._process else None

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *_):
        self.stop()
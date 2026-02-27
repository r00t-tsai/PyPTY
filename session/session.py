import time
from core.conpty    import ConPTY
from process.process   import spawn, ChildProcess
from iobridge.io_bridge import IOBridge


class Session:

    def __init__(
        self,
        shell:    str = "cmd.exe",
        cols:     int = 120,
        rows:     int = 30,
        encoding: str = "utf-8",
    ):
        self._shell    = shell
        self._encoding = encoding
        self._conpty:   ConPTY | None        = None
        self._process:  ChildProcess | None  = None
        self._bridge:   IOBridge | None      = None

    def start(self, cols: int = 120, rows: int = 30):
        self._conpty  = ConPTY(cols, rows)
        self._process = spawn(self._shell, self._conpty.handle)
        self._bridge  = IOBridge(
            self._conpty.read_pipe,
            self._conpty.write_pipe,
            self._encoding,
        )
        self._bridge.start()

    def stop(self):
        if self._bridge:
            self._bridge.stop()
        if self._process:
            try:
                self._process.terminate()
            except Exception:
                pass
            self._process.close_handles()
        if self._conpty:
            self._conpty.close()


    def send_command(self, command: str, delay: float = 0.05):
        if self._bridge:
            self._bridge.send_line(command, self._encoding)
            time.sleep(delay)

    def send_raw(self, data: bytes):
        if self._bridge:
            self._bridge.send(data)

    def resize(self, cols: int, rows: int):
        if self._conpty:
            self._conpty.resize(cols, rows)

    @property
    def pid(self) -> int | None:
        return self._process.pid if self._process else None

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *_):
        self.stop()

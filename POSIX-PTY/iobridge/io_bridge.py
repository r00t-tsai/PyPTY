import os
import sys
import threading
from queue import Queue, Empty


def _fd_read(fd: int, size: int = 4096) -> bytes | None:
    try:
        data = os.read(fd, size)
        return data if data else None
    except OSError:
        return None


def _fd_write(fd: int, data: bytes) -> int:
    try:
        return os.write(fd, data)
    except OSError:
        return 0


class OutputReader(threading.Thread):

    def __init__(self, master_fd: int):
        super().__init__(daemon=True, name="PTY-OutputReader")
        self._fd   = master_fd
        self._stop = threading.Event()

    def stop(self):
        self._stop.set()

    def run(self):
        while not self._stop.is_set():
            data = _fd_read(self._fd)
            if data is None:
                break
            try:
                sys.stdout.buffer.write(data)
                sys.stdout.buffer.flush()
            except Exception:
                break


class InputWriter(threading.Thread):

    def __init__(self, master_fd: int):
        super().__init__(daemon=True, name="PTY-InputWriter")
        self._fd    = master_fd
        self._queue: Queue[bytes] = Queue()
        self._stop  = threading.Event()

    def send(self, data: bytes):
        self._queue.put(data)

    def stop(self):
        self._stop.set()
        self._queue.put(b"")

    def run(self):
        while not self._stop.is_set():
            try:
                data = self._queue.get(timeout=0.1)
            except Empty:
                continue
            if data:
                _fd_write(self._fd, data)


class IOBridge:

    def __init__(self, master_fd: int, encoding: str = "utf-8"):
        self._encoding = encoding
        self._reader   = OutputReader(master_fd)
        self._writer   = InputWriter(master_fd)

    def start(self):
        self._reader.start()
        self._writer.start()

    def send(self, data: bytes):
        self._writer.send(data)

    def send_line(self, text: str, encoding: str | None = None):
        enc = encoding or self._encoding
        self._writer.send((text + "\n").encode(enc))

    def stop(self):
        self._reader.stop()
        self._writer.stop()
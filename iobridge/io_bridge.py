import ctypes
import ctypes.wintypes as wintypes
import sys
import threading
from queue import Queue, Empty

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

def _pipe_read(handle, size: int = 4096) -> bytes | None:
    buf  = (ctypes.c_char * size)()
    read = wintypes.DWORD(0)
    ok   = kernel32.ReadFile(handle, buf, size, ctypes.byref(read), None)
    if not ok or read.value == 0:
        return None
    return bytes(buf[: read.value])


def _pipe_write(handle, data: bytes) -> int:
    written = wintypes.DWORD(0)
    kernel32.WriteFile(handle, data, len(data), ctypes.byref(written), None)
    return written.value

class OutputReader(threading.Thread):

    def __init__(self, read_pipe, encoding: str = "utf-8"):
        super().__init__(daemon=True, name="ConPTY-OutputReader")
        self._pipe     = read_pipe
        self._encoding = encoding
        self._stop     = threading.Event()

    def stop(self):
        self._stop.set()

    def run(self):
        while not self._stop.is_set():
            data = _pipe_read(self._pipe)
            if data is None:
                break
            try:
                sys.stdout.buffer.write(data)
                sys.stdout.buffer.flush()
            except Exception:
                break


class InputWriter(threading.Thread):

    def __init__(self, write_pipe):
        super().__init__(daemon=True, name="ConPTY-InputWriter")
        self._pipe  = write_pipe
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
                _pipe_write(self._pipe, data)


class IOBridge:

    def __init__(self, read_pipe, write_pipe, encoding: str = "utf-8"):
        self._reader = OutputReader(read_pipe, encoding)
        self._writer = InputWriter(write_pipe)

    def start(self):
        self._reader.start()
        self._writer.start()

    def send(self, data: bytes):
        self._writer.send(data)

    def send_line(self, text: str, encoding: str = "utf-8"):
        self._writer.send((text + "\r\n").encode(encoding))

    def stop(self):
        self._reader.stop()
        self._writer.stop()

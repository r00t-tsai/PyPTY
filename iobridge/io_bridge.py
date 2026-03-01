import ctypes
import ctypes.wintypes as wintypes
import re
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


_ANSI_RE = re.compile(
    rb"\x1b(?:"
    rb"\[[0-9;?]*[A-Za-z]"
    rb"|\][^\x07\x1b]*(?:\x07|\x1b\\)"
    rb"|[^[]"
    rb")"
)

def _strip_ansi(data: bytes) -> bytes:
    return _ANSI_RE.sub(b"", data)


_ALWAYS_SUPPRESS = {b"^c", b"control-c"}


class OutputReader(threading.Thread):

    def __init__(self, read_pipe, encoding: str = "utf-8"):
        super().__init__(daemon=True, name="ConPTY-OutputReader")
        self._pipe     = read_pipe
        self._encoding = encoding
        self._stop     = threading.Event()
        self._lock     = threading.Lock()
        self._suppress_queue: list[bytes] = []
        self._last_suppressed: bytes | None = None
        self._banner_done = False
        self._buf = b""

    def suppress_next(self, command: str):
        with self._lock:
            self._suppress_queue.append(
                command.strip().lower().encode(self._encoding)
            )

    def stop(self):
        self._stop.set()

    def _try_suppress(self, key: bytes) -> bool:
        if not key:
            return False
        if key in _ALWAYS_SUPPRESS:
            return True

        if self._last_suppressed and key == self._last_suppressed:
            return True

        with self._lock:
            if self._suppress_queue and self._suppress_queue[0] == key:
                self._last_suppressed = self._suppress_queue.pop(0)
                return True

        if self._last_suppressed and key != self._last_suppressed:
            self._last_suppressed = None

        return False

    def _emit(self, data: bytes):
        if data:
            try:
                sys.stdout.buffer.write(data)
                sys.stdout.buffer.flush()
            except Exception:
                pass

    def _is_prompt_chunk(self, raw: bytes) -> bool:
        cleaned = _strip_ansi(raw).strip()
        return bool(cleaned) and cleaned.endswith(b">")

    def _process(self):
        buf = self._buf

        if not self._banner_done:
            self._emit(buf)
            if self._is_prompt_chunk(buf):
                self._banner_done = True
            self._buf = b""
            return

        out = b""

        while True:
            crlf = buf.find(b"\r\n")
            lf   = buf.find(b"\n")

            if crlf == -1 and lf == -1:
                if buf and self._is_prompt_chunk(buf):
                    out += buf
                    buf  = b""
                break

            if crlf != -1 and (lf == -1 or crlf <= lf):
                content, buf, term = buf[:crlf], buf[crlf + 2:], b"\r\n"
            else:
                content, buf, term = buf[:lf],   buf[lf + 1:],   b"\n"

            key = _strip_ansi(content).strip().lower()
            if self._try_suppress(key):
                continue
            out += content + term

        self._buf = buf
        self._emit(out)

    def run(self):
        while not self._stop.is_set():
            data = _pipe_read(self._pipe)
            if data is None:
                break
            self._buf += data
            self._process()

        if self._buf:
            self._emit(self._buf)
            self._buf = b""


class inputw(threading.Thread):

    def __init__(self, write_pipe):
        super().__init__(daemon=True, name="inputw")
        self._pipe  = write_pipe
        self._queue: Queue[bytes] = Queue()
        self._stop  = threading.Event()

    def send(self, data: bytes):
        self._queue.put(data)

    def send_urgent(self, data: bytes):
        _pipe_write(self._pipe, data)

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
        self._writer = inputw(write_pipe)

    def start(self):
        self._reader.start()
        self._writer.start()

    def send(self, data: bytes):
        self._writer.send(data)

    def send_urgent(self, data: bytes):
        self._writer.send_urgent(data)

    def send_line(self, text: str, encoding: str = "utf-8"):
        self._reader.suppress_next(text)
        self._writer.send((text + "\r\n").encode(encoding))

    def stop(self):
        self._reader.stop()
        self._writer.stop()

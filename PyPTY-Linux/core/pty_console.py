import os
import fcntl
import termios
import struct


class PTYConsole:

    def __init__(self, cols: int = 120, rows: int = 30):
        self.cols = cols
        self.rows = rows
        self._master_fd: int | None = None
        self._slave_fd:  int | None = None
        self._create()

    @property
    def master_fd(self) -> int:
        return self._master_fd

    @property
    def slave_fd(self) -> int:
        return self._slave_fd

    def resize(self, cols: int, rows: int):
        self.cols, self.rows = cols, rows
        winsize = struct.pack("HHHH", rows, cols, 0, 0)
        fcntl.ioctl(self._master_fd, termios.TIOCSWINSZ, winsize)

    def close(self):
        for fd in (self._master_fd, self._slave_fd):
            if fd is not None:
                try:
                    os.close(fd)
                except OSError:
                    pass
        self._master_fd = self._slave_fd = None

    def _create(self):
        self._master_fd, self._slave_fd = os.openpty()
        self.resize(self.cols, self.rows)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
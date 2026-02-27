import ctypes
import ctypes.wintypes as wintypes
import os

PROC_THREAD_ATTRIBUTE_PSEUDOCONSOLE = 0x00020016
EXTENDED_STARTUPINFO_PRESENT        = 0x00080000
CREATE_UNICODE_ENVIRONMENT          = 0x00000400

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

class COORD(ctypes.Structure):
    _fields_ = [("X", ctypes.c_short), ("Y", ctypes.c_short)]


class STARTUPINFOEX(ctypes.Structure):
    _fields_ = [
        ("StartupInfo",  ctypes.c_byte * 104),  
        ("lpAttributeList", ctypes.c_void_p),
    ]

class ConPTY:

    def __init__(self, cols: int = 120, rows: int = 30):
        self.cols = cols
        self.rows = rows
        self.handle = None          
        self._pipe_read_in  = None 
        self._pipe_write_in = None
        self._pipe_read_out = None
        self._pipe_write_out = None
        self._create()

    @property
    def write_pipe(self):
        return self._pipe_write_in

    @property
    def read_pipe(self):
        return self._pipe_read_out

    def resize(self, cols: int, rows: int):
        coord = COORD(cols, rows)
        ret = kernel32.ResizePseudoConsole(self.handle, coord)
        if ret != 0:
            raise ctypes.WinError(ret)
        self.cols, self.rows = cols, rows

    def close(self):
        if self.handle:
            kernel32.ClosePseudoConsole(self.handle)
            self.handle = None
        for h in (self._pipe_write_in, self._pipe_read_out,
                  self._pipe_read_in, self._pipe_write_out):
            if h and h != wintypes.HANDLE(-1):
                try:
                    kernel32.CloseHandle(h)
                except Exception:
                    pass
        self._pipe_write_in = self._pipe_read_out = None
        self._pipe_read_in  = self._pipe_write_out = None

    def _create_pipes(self):

        SECURITY_ATTRIBUTES = ctypes.c_byte * 12 
        null = None

        read_in  = wintypes.HANDLE()
        write_in = wintypes.HANDLE()
        read_out = wintypes.HANDLE()
        write_out = wintypes.HANDLE()

        if not kernel32.CreatePipe(ctypes.byref(read_in),  ctypes.byref(write_in),  null, 0):
            raise ctypes.WinError(ctypes.get_last_error())
        if not kernel32.CreatePipe(ctypes.byref(read_out), ctypes.byref(write_out), null, 0):
            raise ctypes.WinError(ctypes.get_last_error())

        self._pipe_read_in   = read_in
        self._pipe_write_in  = write_in
        self._pipe_read_out  = read_out
        self._pipe_write_out = write_out

    def _create(self):
        self._create_pipes()
        coord = COORD(self.cols, self.rows)
        hpc   = ctypes.c_void_p()

        ret = kernel32.CreatePseudoConsole(
            coord,
            self._pipe_read_in,
            self._pipe_write_out,
            0,
            ctypes.byref(hpc),
        )
        if ret != 0:
            raise ctypes.WinError(ret)
        self.handle = hpc

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

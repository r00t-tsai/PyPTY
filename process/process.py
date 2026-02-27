import ctypes
import ctypes.wintypes as wintypes

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

PROC_THREAD_ATTRIBUTE_PSEUDOCONSOLE = 0x00020016
EXTENDED_STARTUPINFO_PRESENT        = 0x00080000
CREATE_UNICODE_ENVIRONMENT          = 0x00000400

class STARTUPINFOEX(ctypes.Structure):
    class _STARTUPINFOW(ctypes.Structure):
        _fields_ = [
            ("cb",              wintypes.DWORD),
            ("lpReserved",      wintypes.LPWSTR),
            ("lpDesktop",       wintypes.LPWSTR),
            ("lpTitle",         wintypes.LPWSTR),
            ("dwX",             wintypes.DWORD),
            ("dwY",             wintypes.DWORD),
            ("dwXSize",         wintypes.DWORD),
            ("dwYSize",         wintypes.DWORD),
            ("dwXCountChars",   wintypes.DWORD),
            ("dwYCountChars",   wintypes.DWORD),
            ("dwFillAttribute", wintypes.DWORD),
            ("dwFlags",         wintypes.DWORD),
            ("wShowWindow",     wintypes.WORD),
            ("cbReserved2",     wintypes.WORD),
            ("lpReserved2",     ctypes.POINTER(ctypes.c_byte)),
            ("hStdInput",       wintypes.HANDLE),
            ("hStdOutput",      wintypes.HANDLE),
            ("hStdError",       wintypes.HANDLE),
        ]

    _fields_ = [
        ("StartupInfo",     _STARTUPINFOW),
        ("lpAttributeList", ctypes.c_void_p),
    ]


class PROCESS_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("hProcess",    wintypes.HANDLE),
        ("hThread",     wintypes.HANDLE),
        ("dwProcessId", wintypes.DWORD),
        ("dwThreadId",  wintypes.DWORD),
    ]


class ChildProcess:

    def __init__(self, proc_info: PROCESS_INFORMATION):
        self._info = proc_info

    @property
    def pid(self) -> int:
        return self._info.dwProcessId

    def wait(self, timeout_ms: int = 0xFFFFFFFF) -> int:
        kernel32.WaitForSingleObject(self._info.hProcess, timeout_ms)
        code = wintypes.DWORD()
        kernel32.GetExitCodeProcess(self._info.hProcess, ctypes.byref(code))
        return code.value

    def terminate(self):
        kernel32.TerminateProcess(self._info.hProcess, 1)

    def close_handles(self):
        kernel32.CloseHandle(self._info.hProcess)
        kernel32.CloseHandle(self._info.hThread)


def spawn(command: str, conpty_handle) -> ChildProcess:

    attr_list_size = ctypes.c_size_t(0)
    kernel32.InitializeProcThreadAttributeList(None, 1, 0, ctypes.byref(attr_list_size))
    attr_list_buf = (ctypes.c_byte * attr_list_size.value)()
    if not kernel32.InitializeProcThreadAttributeList(attr_list_buf, 1, 0, ctypes.byref(attr_list_size)):
        raise ctypes.WinError(ctypes.get_last_error())

    hpcon_val = ctypes.c_void_p(conpty_handle.value if hasattr(conpty_handle, 'value') else int(conpty_handle))

    if not kernel32.UpdateProcThreadAttribute(
        attr_list_buf,
        0,
        PROC_THREAD_ATTRIBUTE_PSEUDOCONSOLE,
        hpcon_val,
        ctypes.sizeof(hpcon_val),
        None,
        None,
    ):
        raise ctypes.WinError(ctypes.get_last_error())

    si = STARTUPINFOEX()
    si.StartupInfo.cb = ctypes.sizeof(si)
    si.lpAttributeList = ctypes.cast(attr_list_buf, ctypes.c_void_p)

    pi = PROCESS_INFORMATION()

    flags = EXTENDED_STARTUPINFO_PRESENT | CREATE_UNICODE_ENVIRONMENT

    if not kernel32.CreateProcessW(
        None,
        command,
        None, None,
        False,
        flags,
        None, None,
        ctypes.byref(si),
        ctypes.byref(pi),
    ):
        raise ctypes.WinError(ctypes.get_last_error())

    kernel32.DeleteProcThreadAttributeList(attr_list_buf)
    return ChildProcess(pi)

"""Attach once per thread; avoid desktop handle leaks during long sessions."""
import atexit
import ctypes
from ctypes import wintypes
import threading

u32 = ctypes.windll.user32
u32.OpenInputDesktop.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
u32.OpenInputDesktop.restype = wintypes.HANDLE
u32.SetThreadDesktop.argtypes = [wintypes.HANDLE]
u32.CloseDesktop.argtypes = [wintypes.HANDLE]
u32.GetThreadDesktop.argtypes = [wintypes.DWORD]
u32.GetThreadDesktop.restype = wintypes.HANDLE
_local = threading.local()
_dpi_ready = False


def init_dpi():
    global _dpi_ready
    if _dpi_ready:
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (AttributeError, OSError):
        u32.SetProcessDPIAware()
    _dpi_ready = True


def attach_input_desktop():
    if getattr(_local, "handle", None):
        return _local.handle
    original = u32.GetThreadDesktop(ctypes.windll.kernel32.GetCurrentThreadId())
    handle = u32.OpenInputDesktop(0, False, 0x01FF)
    if handle:
        if u32.SetThreadDesktop(handle):
            _local.handle = handle
            _local.original = original
            return handle
        u32.CloseDesktop(handle)
    return None


def _cleanup():
    handle = getattr(_local, "handle", None)
    if handle and u32.SetThreadDesktop(_local.original):
        u32.CloseDesktop(handle)


atexit.register(_cleanup)

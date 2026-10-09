"""
Native Win32 Visual Overlay for Computer Use
Draws a glowing Google-colored screen border, status banner, and cursor halo.
100% click-through, non-activating, zero console windows.
"""

import sys
import os
import time
import argparse
import ctypes
from win_desktop import attach_input_desktop
from win_desktop import init_dpi
import getpass
from ctypes import wintypes

u32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
k32 = ctypes.windll.kernel32

CLASS_NAME = "ComputerUseOverlay-" + getpass.getuser()
_process = None
# Declare handle/pointer signatures for 64-bit Python.
def _api(dll, name, result, args):
    fn = getattr(dll, name)
    fn.restype, fn.argtypes = result, args

_api(k32, "GetModuleHandleW", wintypes.HMODULE, [wintypes.LPCWSTR])
_api(k32, "CreateMutexW", wintypes.HANDLE, [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR])
_api(k32, "CloseHandle", wintypes.BOOL, [wintypes.HANDLE])
_api(u32, "FindWindowW", wintypes.HWND, [wintypes.LPCWSTR, wintypes.LPCWSTR])
_api(u32, "CreateWindowExW", wintypes.HWND, [wintypes.DWORD, wintypes.LPCWSTR,
    wintypes.LPCWSTR, wintypes.DWORD, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    ctypes.c_int, wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, ctypes.c_void_p])
_api(u32, "OpenInputDesktop", wintypes.HANDLE, [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD])
_api(u32, "SetThreadDesktop", wintypes.BOOL, [wintypes.HANDLE])
_api(u32, "CloseDesktop", wintypes.BOOL, [wintypes.HANDLE])
_api(u32, "BeginPaint", wintypes.HDC, [wintypes.HWND, ctypes.c_void_p])
_api(u32, "EndPaint", wintypes.BOOL, [wintypes.HWND, ctypes.c_void_p])
_api(u32, "SetLayeredWindowAttributes", wintypes.BOOL, [wintypes.HWND, wintypes.DWORD, wintypes.BYTE, wintypes.DWORD])
_api(u32, "SetTimer", ctypes.c_size_t, [wintypes.HWND, ctypes.c_size_t, wintypes.UINT, ctypes.c_void_p])
_api(u32, "ShowWindow", wintypes.BOOL, [wintypes.HWND, ctypes.c_int])
_api(u32, "UpdateWindow", wintypes.BOOL, [wintypes.HWND])
_api(u32, "DestroyWindow", wintypes.BOOL, [wintypes.HWND])
_api(u32, "InvalidateRect", wintypes.BOOL, [wintypes.HWND, ctypes.c_void_p, wintypes.BOOL])
_api(u32, "FillRect", ctypes.c_int, [wintypes.HDC, ctypes.c_void_p, wintypes.HBRUSH])
_api(u32, "DrawTextW", ctypes.c_int, [wintypes.HDC, wintypes.LPCWSTR, ctypes.c_int, ctypes.c_void_p, wintypes.UINT])
_api(u32, "PostMessageW", wintypes.BOOL, [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM])
_api(u32, "GetWindowThreadProcessId", wintypes.DWORD, [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)])
_api(gdi32, "CreateSolidBrush", wintypes.HBRUSH, [wintypes.DWORD])
_api(gdi32, "CreatePen", wintypes.HANDLE, [ctypes.c_int, ctypes.c_int, wintypes.DWORD])
_api(gdi32, "SelectObject", wintypes.HANDLE, [wintypes.HDC, wintypes.HANDLE])
_api(gdi32, "GetStockObject", wintypes.HANDLE, [ctypes.c_int])
_api(gdi32, "DeleteObject", wintypes.BOOL, [wintypes.HANDLE])
_api(gdi32, "Ellipse", wintypes.BOOL, [wintypes.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int])
_api(gdi32, "SetBkMode", ctypes.c_int, [wintypes.HDC, ctypes.c_int])
_api(gdi32, "SetTextColor", wintypes.DWORD, [wintypes.HDC, wintypes.DWORD])
_api(gdi32, "CreateFontW", wintypes.HANDLE, [ctypes.c_int] * 5 + [wintypes.DWORD] * 8 + [wintypes.LPCWSTR])

# Window styles
WS_POPUP = 0x80000000
WS_VISIBLE = 0x10000000
WS_EX_TOPMOST = 0x00000008
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_LAYERED = 0x00080000
WS_EX_NOACTIVATE = 0x08000000

LWA_COLORKEY = 0x00000001
COLORKEY = 0x00010000  # RGB(0, 0, 1)

# Google Colors in Win32 COLORREF (0x00BBGGRR)
COLOR_BLUE = 0x00F48542
COLOR_RED = 0x003543EA
COLOR_YELLOW = 0x0005BCFB
COLOR_GREEN = 0x0053A834
COLOR_DARK = 0x00201F1E
COLOR_WHITE = 0x00FFFFFF
u32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
u32.DefWindowProcW.restype = wintypes.LPARAM

WNDPROC = ctypes.WINFUNCTYPE(wintypes.LPARAM, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)

class Overlay:
    def __init__(self, duration=None):
        init_dpi()
        attach_input_desktop()
        self.duration = duration
        self.start_time = time.monotonic()
        self.w = u32.GetSystemMetrics(0)
        self.h = u32.GetSystemMetrics(1)
        self.last_cursor = (0, 0)
        self.cursor_color_idx = 0
        self.hwnd = None

    def create_window(self):
        wc_name = CLASS_NAME

        class WNDCLASSEXW(ctypes.Structure):
            _fields_ = [
                ("cbSize", wintypes.UINT),
                ("style", wintypes.UINT),
                ("lpfnWndProc", WNDPROC),
                ("cbClsExtra", ctypes.c_int),
                ("cbWndExtra", ctypes.c_int),
                ("hInstance", wintypes.HINSTANCE),
                ("hIcon", wintypes.HICON),
                ("hCursor", wintypes.HANDLE),
                ("hbrBackground", wintypes.HBRUSH),
                ("lpszMenuName", wintypes.LPCWSTR),
                ("lpszClassName", wintypes.LPCWSTR),
                ("hIconSm", wintypes.HICON)
            ]

        def wnd_proc(hwnd, msg, wparam, lparam):
            if msg == 0x000F:  # WM_PAINT
                self.on_paint(hwnd)
                return 0
            elif msg == 0x0113:  # WM_TIMER
                self.on_timer(hwnd)
                return 0
            elif msg == 0x0002:  # WM_DESTROY
                u32.PostQuitMessage(0)
                return 0
            return u32.DefWindowProcW(hwnd, msg, wparam, lparam)

        self._proc = WNDPROC(wnd_proc)

        # Transparent background brush
        bg_brush = gdi32.CreateSolidBrush(0x00010000)

        wc = WNDCLASSEXW()
        wc.cbSize = ctypes.sizeof(WNDCLASSEXW)
        wc.style = 3  # CS_HREDRAW | CS_VREDRAW
        wc.lpfnWndProc = self._proc
        wc.hInstance = k32.GetModuleHandleW(None)
        wc.hbrBackground = bg_brush
        wc.lpszClassName = wc_name

        u32.RegisterClassExW.argtypes = [ctypes.c_void_p]
        if not u32.RegisterClassExW(ctypes.byref(wc)):
            raise ctypes.WinError()

        ex_style = WS_EX_TOPMOST | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW | WS_EX_LAYERED | WS_EX_NOACTIVATE
        style = WS_POPUP | WS_VISIBLE

        self.hwnd = u32.CreateWindowExW(
            ex_style,
            wc_name,
            "Computer Use",
            style,
            0, 0, self.w, self.h,
            0, 0, wc.hInstance, None
        )

        if not self.hwnd:
            raise ctypes.WinError()
        self._bg_brush = bg_brush
        self._font = gdi32.CreateFontW(-15, 0, 0, 0, 500, 0, 0, 0, 1, 0, 0, 5, 0, "Segoe UI")
        # Hide the indicator from captured screenshots when Windows supports it.
        try:
            u32.SetWindowDisplayAffinity.argtypes = [wintypes.HWND, wintypes.DWORD]
            u32.SetWindowDisplayAffinity(self.hwnd, 0x11)
        except AttributeError:
            pass

        # Set transparency color key
        u32.SetLayeredWindowAttributes(self.hwnd, COLORKEY, 0, LWA_COLORKEY)

        # 30 FPS cursor tracking; stationary frames do not repaint.
        u32.SetTimer(self.hwnd, 1, 33, None)

        u32.ShowWindow(self.hwnd, 5)
        u32.UpdateWindow(self.hwnd)

    def on_paint(self, hwnd):
        class PAINTSTRUCT(ctypes.Structure):
            _fields_ = [
                ('hdc', wintypes.HDC),
                ('fErase', wintypes.BOOL),
                ('rcPaint', wintypes.RECT),
                ('fRestore', wintypes.BOOL),
                ('fIncUpdate', wintypes.BOOL),
                ('rgbReserved', wintypes.BYTE * 32)
            ]

        ps = PAINTSTRUCT()
        hdc = u32.BeginPaint(hwnd, ctypes.byref(ps))
        old_font = gdi32.SelectObject(hdc, self._font) if self._font else None

        w, h = self.w, self.h
        bw = 6  # Border width
        q = w // 4

        def fill_box(x1, y1, x2, y2, color):
            brush = gdi32.CreateSolidBrush(color)
            rect = wintypes.RECT(x1, y1, x2, y2)
            u32.FillRect(hdc, ctypes.byref(rect), brush)
            gdi32.DeleteObject(brush)

        # 1. Top border: Blue -> Red -> Yellow -> Green
        fill_box(0, 0, q, bw, COLOR_BLUE)
        fill_box(q, 0, q * 2, bw, COLOR_RED)
        fill_box(q * 2, 0, q * 3, bw, COLOR_YELLOW)
        fill_box(q * 3, 0, w, bw, COLOR_GREEN)

        # 2. Right border: Green
        fill_box(w - bw, 0, w, h, COLOR_GREEN)

        # 3. Bottom border: Green -> Yellow -> Red -> Blue
        fill_box(q * 3, h - bw, w, h, COLOR_GREEN)
        fill_box(q * 2, h - bw, q * 3, h, COLOR_YELLOW)
        fill_box(q, h - bw, q * 2, h, COLOR_RED)
        fill_box(0, h - bw, q, h, COLOR_BLUE)

        # 4. Left border: Blue
        fill_box(0, 0, bw, h, COLOR_BLUE)

        # 5. Top Status Pill Badge
        pw, ph = min(440, w - 24), 36
        px1 = (w - pw) // 2
        px2 = px1 + pw
        py1 = bw
        py2 = py1 + ph

        # Dark badge background
        fill_box(px1, py1, px2, py2, COLOR_DARK)
        # Outline in Google Blue
        fill_box(px1, py1, px2, py1 + 2, COLOR_BLUE)
        fill_box(px1, py2 - 2, px2, py2, COLOR_BLUE)
        fill_box(px1, py1, px1 + 2, py2, COLOR_BLUE)
        fill_box(px2 - 2, py1, px2, py2, COLOR_BLUE)

        # 4 Google colored indicator squares inside the pill
        dot_y = py1 + 10
        dot_sz = 10
        fill_box(px1 + 14, dot_y, px1 + 14 + dot_sz, dot_y + dot_sz, COLOR_BLUE)
        fill_box(px1 + 28, dot_y, px1 + 28 + dot_sz, dot_y + dot_sz, COLOR_RED)
        fill_box(px1 + 42, dot_y, px1 + 42 + dot_sz, dot_y + dot_sz, COLOR_YELLOW)
        fill_box(px1 + 56, dot_y, px1 + 56 + dot_sz, dot_y + dot_sz, COLOR_GREEN)

        # Text inside pill
        gdi32.SetBkMode(hdc, 1)  # TRANSPARENT
        gdi32.SetTextColor(hdc, COLOR_WHITE)
        txt = "AI controls this computer | Esc: cancel"
        rect_txt = wintypes.RECT(px1 + 72, py1 + 7, px2 - 6, py2)
        u32.DrawTextW(hdc, txt, -1, ctypes.byref(rect_txt), 0x0000)

        # 6. Draw Cursor Follower Halo
        cx, cy = self.last_cursor
        r = 16
        cursor_colors = [COLOR_BLUE, COLOR_RED, COLOR_YELLOW, COLOR_GREEN]
        cur_col = cursor_colors[self.cursor_color_idx % len(cursor_colors)]

        # Draw circle ring around cursor using hollow brush + colored pen
        pen = gdi32.CreatePen(0, 3, cur_col)
        old_pen = gdi32.SelectObject(hdc, pen)
        old_brush = gdi32.SelectObject(hdc, gdi32.GetStockObject(5))  # NULL_BRUSH
        gdi32.Ellipse(hdc, cx - r, cy - r, cx + r, cy + r)

        # Center dot
        dot_pen = gdi32.CreatePen(0, 1, COLOR_WHITE)
        dot_brush = gdi32.CreateSolidBrush(COLOR_WHITE)
        gdi32.SelectObject(hdc, dot_pen)
        gdi32.SelectObject(hdc, dot_brush)
        gdi32.Ellipse(hdc, cx - 2, cy - 2, cx + 2, cy + 2)

        gdi32.SelectObject(hdc, old_pen)
        gdi32.SelectObject(hdc, old_brush)
        gdi32.DeleteObject(pen)
        gdi32.DeleteObject(dot_pen)
        gdi32.DeleteObject(dot_brush)

        if old_font:
            gdi32.SelectObject(hdc, old_font)
        u32.EndPaint(hwnd, ctypes.byref(ps))

    def on_timer(self, hwnd):
        # Check duration
        if self.duration and (time.monotonic() - self.start_time) >= self.duration:
            u32.DestroyWindow(hwnd)
            return

        if u32.GetAsyncKeyState(0x1B) & 0x8000:
            u32.DestroyWindow(hwnd)
            return

        # Check cursor position
        pt = wintypes.POINT()
        u32.GetCursorPos(ctypes.byref(pt))
        cx, cy = pt.x, pt.y

        # Invalidate old cursor region and new cursor region
        old_x, old_y = self.last_cursor
        r = 24
        rect_old = wintypes.RECT(old_x - r, old_y - r, old_x + r, old_y + r)
        rect_new = wintypes.RECT(cx - r, cy - r, cx + r, cy + r)

        if (cx, cy) == self.last_cursor:
            return
        self.last_cursor = (cx, cy)
        self.cursor_color_idx = (self.cursor_color_idx + 1) % 4

        u32.InvalidateRect(hwnd, ctypes.byref(rect_old), True)
        u32.InvalidateRect(hwnd, ctypes.byref(rect_new), True)

    def run(self):
        mutex = k32.CreateMutexW(None, False, "Local\\" + CLASS_NAME)
        if not mutex:
            raise ctypes.WinError()
        if k32.GetLastError() == 183:
            k32.CloseHandle(mutex)
            return
        try:
            self.create_window()
            msg = wintypes.MSG()
            while u32.GetMessageW(ctypes.byref(msg), 0, 0, 0) > 0:
                u32.TranslateMessage(ctypes.byref(msg))
                u32.DispatchMessageW(ctypes.byref(msg))
        finally:
            if hasattr(self, "_bg_brush"):
                gdi32.DeleteObject(self._bg_brush)
            if getattr(self, "_font", None):
                gdi32.DeleteObject(self._font)
            k32.CloseHandle(mutex)


def overlay_status():
    hwnd = u32.FindWindowW(CLASS_NAME, None)
    pid = wintypes.DWORD()
    if hwnd:
        u32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return {"running": bool(hwnd), "pid": pid.value if hwnd else None}


def start_overlay(duration=None):
    global _process
    state = overlay_status()
    if state["running"]:
        return state["pid"]
    import subprocess
    cmd = [sys.executable, os.path.abspath(__file__), "run"]
    if duration is not None:
        if duration <= 0:
            raise ValueError("Overlay duration must be positive")
        cmd.extend(["--duration", str(duration)])
    proc = subprocess.Popen(cmd, creationflags=subprocess.CREATE_NO_WINDOW,
                            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL, close_fds=True,
                            cwd=os.path.dirname(os.path.abspath(__file__)))
    _process = proc
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        state = overlay_status()
        if state["running"]:
            return state["pid"]
        if proc.poll() is not None:
            raise RuntimeError("Overlay failed to start")
        time.sleep(0.02)
    proc.terminate()
    raise RuntimeError("Overlay startup timed out")


def stop_overlay():
    global _process
    hwnd = u32.FindWindowW(CLASS_NAME, None)
    if not hwnd:
        return False
    # Graceful close of our own window; never taskkill a potentially reused PID.
    u32.PostMessageW(hwnd, 0x0010, 0, 0)
    deadline = time.monotonic() + 2
    while overlay_status()["running"] and time.monotonic() < deadline:
        time.sleep(0.02)
    if _process and not overlay_status()["running"]:
        try:
            _process.wait(timeout=1)
            _process = None
        except __import__("subprocess").TimeoutExpired:
            pass
    return not overlay_status()["running"]


def main():
    parser = argparse.ArgumentParser(description="Computer Use Native Win32 Visual Overlay")
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_run = subparsers.add_parser("run")
    p_run.add_argument("--duration", type=float, default=None)

    p_start = subparsers.add_parser("start")
    p_start.add_argument("--duration", type=float, default=None)

    subparsers.add_parser("stop")
    subparsers.add_parser("status")

    args = parser.parse_args()

    if args.command == "run":
        overlay = Overlay(duration=args.duration)
        overlay.run()
    elif args.command == "start":
        pid = start_overlay(duration=args.duration)
        print(f"Overlay started (PID: {pid})")
    elif args.command == "stop":
        stopped = stop_overlay()
        print("Overlay stopped." if stopped else "Overlay not running.")
    elif args.command == "status":
        import json
        print(json.dumps(overlay_status()))

if __name__ == "__main__":
    main()

"""
Window Management Module for Computer Use
Allows listing, locating, focusing, and controlling application windows
on the active Windows interactive desktop.
"""

import sys
import argparse
import ctypes
import json
import os

u32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

SW_HIDE = 0
SW_SHOWNORMAL = 1
SW_SHOWMINIMIZED = 2
SW_MAXIMIZE = 3
SW_SHOWNOACTIVATE = 4
SW_SHOW = 5
SW_MINIMIZE = 6
SW_RESTORE = 9

WM_CLOSE = 0x0010

def init_dpi():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PROCESS_PER_MONITOR_DPI_AWARE
    except Exception:
        try:
            u32.SetProcessDPIAware()
        except Exception:
            pass

def attach_input_desktop():
    try:
        hinput = u32.OpenInputDesktop(0, False, 0x01FF)
        if hinput:
            u32.SetThreadDesktop(hinput)
            return hinput
    except Exception:
        pass
    return None

class RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long)
    ]

def get_process_name(pid):
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    hproc = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not hproc:
        return ""
    buf = ctypes.create_unicode_buffer(1024)
    size = ctypes.c_uint32(1024)
    try:
        if kernel32.QueryFullProcessImageNameW(hproc, 0, buf, ctypes.byref(size)):
            return os.path.basename(buf.value)
    finally:
        kernel32.CloseHandle(hproc)
    return ""

def list_windows(include_hidden=False):
    init_dpi()
    hinput = attach_input_desktop()

    windows = []
    fg_hwnd = u32.GetForegroundWindow()

    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

    def enum_cb(hwnd, lparam):
        # Must be visible unless hidden requested
        if not include_hidden and not u32.IsWindowVisible(hwnd):
            return True

        length = u32.GetWindowTextLengthW(hwnd)
        if length == 0:
            return True

        title_buf = ctypes.create_unicode_buffer(length + 1)
        u32.GetWindowTextW(hwnd, title_buf, length + 1)
        title = title_buf.value.strip()
        if not title:
            return True

        # Bounding box
        rect = RECT()
        u32.GetWindowRect(hwnd, ctypes.byref(rect))
        w = rect.right - rect.left
        h = rect.bottom - rect.top

        # Exclude 0-sized tooltips or off-screen invisible artifacts
        if not include_hidden and (w <= 0 or h <= 0):
            return True

        pid = ctypes.c_ulong()
        u32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        pname = get_process_name(pid.value)

        is_minimized = bool(u32.IsIconic(hwnd))
        is_active = (hwnd == fg_hwnd)

        windows.append({
            "hwnd": hwnd,
            "title": title,
            "process": pname,
            "pid": pid.value,
            "bounds": [rect.left, rect.top, rect.right, rect.bottom],
            "width": w,
            "height": h,
            "minimized": is_minimized,
            "active": is_active
        })
        return True

    cb = WNDENUMPROC(enum_cb)
    u32.EnumDesktopWindows(hinput if hinput else 0, cb, 0)
    return windows

def find_window(query):
    query_lower = query.lower()
    wins = list_windows(include_hidden=False)

    # 1. Exact match on title or process
    for w in wins:
        if w["title"].lower() == query_lower or w["process"].lower() == query_lower:
            return w

    # 2. Substring match
    for w in wins:
        if query_lower in w["title"].lower() or query_lower in w["process"].lower():
            return w

    return None

def focus_window(query):
    init_dpi()
    attach_input_desktop()
    target = find_window(query)
    if not target:
        raise ValueError(f"No active window matching '{query}' found")

    hwnd = target["hwnd"]

    # If minimized, restore first
    if target["minimized"]:
        u32.ShowWindow(hwnd, SW_RESTORE)

    # Bypass Windows SetForegroundWindow restrictions by attaching thread input
    cur_thread = kernel32.GetCurrentThreadId()
    target_thread = u32.GetWindowThreadProcessId(hwnd, 0)

    u32.AttachThreadInput(cur_thread, target_thread, True)
    u32.BringWindowToTop(hwnd)
    u32.ShowWindow(hwnd, SW_SHOW)
    u32.SetForegroundWindow(hwnd)
    u32.SetFocus(hwnd)
    u32.AttachThreadInput(cur_thread, target_thread, False)

    return target

def minimize_window(query):
    init_dpi()
    attach_input_desktop()
    target = find_window(query)
    if not target:
        raise ValueError(f"No active window matching '{query}' found")
    u32.ShowWindow(target["hwnd"], SW_MINIMIZE)
    return target

def maximize_window(query):
    init_dpi()
    attach_input_desktop()
    target = find_window(query)
    if not target:
        raise ValueError(f"No active window matching '{query}' found")
    u32.ShowWindow(target["hwnd"], SW_MAXIMIZE)
    return target

def get_active_window():
    init_dpi()
    attach_input_desktop()
    fg_hwnd = u32.GetForegroundWindow()
    if not fg_hwnd:
        return None

    length = u32.GetWindowTextLengthW(fg_hwnd)
    title = ""
    if length > 0:
        title_buf = ctypes.create_unicode_buffer(length + 1)
        u32.GetWindowTextW(fg_hwnd, title_buf, length + 1)
        title = title_buf.value

    rect = RECT()
    u32.GetWindowRect(fg_hwnd, ctypes.byref(rect))

    pid = ctypes.c_ulong()
    u32.GetWindowThreadProcessId(fg_hwnd, ctypes.byref(pid))
    pname = get_process_name(pid.value)

    return {
        "hwnd": fg_hwnd,
        "title": title,
        "process": pname,
        "pid": pid.value,
        "bounds": [rect.left, rect.top, rect.right, rect.bottom],
        "width": rect.right - rect.left,
        "height": rect.bottom - rect.top,
        "active": True
    }

def main():
    parser = argparse.ArgumentParser(description="Computer Use Window Management")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # list
    p_list = subparsers.add_parser("list", help="List active desktop windows")
    p_list.add_argument("--all", action="store_true", help="Include hidden windows")

    # active
    subparsers.add_parser("active", help="Get current active foreground window")

    # focus
    p_focus = subparsers.add_parser("focus", help="Bring window to front and focus")
    p_focus.add_argument("query", help="Title substring or process name")

    # minimize
    p_min = subparsers.add_parser("minimize", help="Minimize window")
    p_min.add_argument("query", help="Title substring or process name")

    # maximize
    p_max = subparsers.add_parser("maximize", help="Maximize window")
    p_max.add_argument("query", help="Title substring or process name")

    parser.add_argument("--json", action="store_true", help="Output JSON result")

    args = parser.parse_args()

    try:
        res = None
        cmd = args.command

        if cmd == "list":
            res = list_windows(include_hidden=args.all)
        elif cmd == "active":
            res = get_active_window()
        elif cmd == "focus":
            res = focus_window(args.query)
        elif cmd == "minimize":
            res = minimize_window(args.query)
        elif cmd == "maximize":
            res = maximize_window(args.query)

        if args.json:
            print(json.dumps(res, indent=2 if not isinstance(res, list) else None))
        else:
            if cmd == "list":
                print(f"Active Desktop Windows ({len(res)} found):")
                print("-" * 75)
                for w in res:
                    act = " [ACTIVE]" if w["active"] else ""
                    min_str = " (minimized)" if w["minimized"] else ""
                    print(f"[{w['process'] or 'Unknown'}] HWND:{w['hwnd']} '{w['title'][:50]}'{min_str}{act}")
                    print(f"   Bounds: ({w['bounds'][0]}, {w['bounds'][1]}) -> ({w['bounds'][2]}, {w['bounds'][3]}) | Size: {w['width']}x{w['height']}")
            elif cmd == "active":
                if res:
                    print(f"Active Window: [{res['process']}] '{res['title']}' HWND:{res['hwnd']}")
                else:
                    print("No active foreground window detected.")
            else:
                print(f"Window Action '{cmd}' completed: {res['title']} (HWND: {res['hwnd']})")

    except Exception as e:
        if args.json:
            print(json.dumps({"error": str(e)}))
        else:
            print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()

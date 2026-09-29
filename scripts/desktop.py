"""
Desktop Icon Manager for Computer Use
Directly queries the Windows Explorer SysListView32 desktop control
to resolve icon names to exact (X, Y) physical coordinates in milliseconds.
Enables instant sub-second desktop automation without trial-and-error cropping.
"""

import sys
import os
import time
import argparse
import ctypes
from ctypes import wintypes
import json

u32 = ctypes.windll.user32
k32 = ctypes.windll.kernel32

def init_dpi():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
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

def find_desktop_listview():
    init_dpi()
    attach_input_desktop()

    h_prog = u32.FindWindowW("Progman", None)
    h_dv = u32.FindWindowExW(h_prog, 0, "SHELLDLL_DefView", None)
    if not h_dv:
        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
        def enum_cb(hwnd, lparam):
            dv = u32.FindWindowExW(hwnd, 0, "SHELLDLL_DefView", None)
            if dv:
                ctypes.cast(lparam, ctypes.POINTER(wintypes.HWND))[0] = dv
                return False
            return True
        cb = WNDENUMPROC(enum_cb)
        found_dv = wintypes.HWND(0)
        u32.EnumWindows(cb, ctypes.byref(found_dv))
        h_dv = found_dv.value

    if h_dv:
        return u32.FindWindowExW(h_dv, 0, "SysListView32", None)
    return None

class LVITEMW(ctypes.Structure):
    _fields_ = [
        ('mask', wintypes.UINT),
        ('iItem', ctypes.c_int),
        ('iSubItem', ctypes.c_int),
        ('state', wintypes.UINT),
        ('stateMask', wintypes.UINT),
        ('pszText', ctypes.c_void_p),
        ('cchTextMax', ctypes.c_int),
        ('iImage', ctypes.c_int),
        ('lParam', ctypes.c_void_p),
        ('iIndent', ctypes.c_int),
        ('iGroupId', ctypes.c_int),
        ('cColumns', wintypes.UINT),
        ('puColumns', ctypes.c_void_p),
        ('piColFmt', ctypes.c_void_p),
        ('iGroup', ctypes.c_int)
    ]

class POINT(ctypes.Structure):
    _fields_ = [('x', ctypes.c_long), ('y', ctypes.c_long)]

def get_desktop_icons():
    """Returns a list of dicts: [{'name': str, 'x': int, 'y': int}] for all desktop items."""
    init_dpi()
    attach_input_desktop()
    lv = find_desktop_listview()
    if not lv:
        return []

    LVM_GETITEMCOUNT = 0x1004
    LVM_GETITEMPOSITION = 0x1010
    LVM_GETITEMTEXTW = 0x1073

    count = u32.SendMessageW(lv, LVM_GETITEMCOUNT, 0, 0)
    if count <= 0:
        return []

    pid = wintypes.DWORD()
    u32.GetWindowThreadProcessId(lv, ctypes.byref(pid))

    PROCESS_VM_OPERATION = 0x0008
    PROCESS_VM_READ = 0x0010
    PROCESS_VM_WRITE = 0x0020
    hproc = k32.OpenProcess(PROCESS_VM_OPERATION | PROCESS_VM_READ | PROCESS_VM_WRITE, False, pid)
    if not hproc:
        return []

    icons = []
    try:
        sz_item = ctypes.sizeof(LVITEMW)
        text_buf_sz = 512
        pt_sz = ctypes.sizeof(POINT)
        total_alloc = sz_item + text_buf_sz + pt_sz

        p_remote = k32.VirtualAllocEx(hproc, 0, total_alloc, 0x1000, 4)
        if not p_remote:
            return []

        p_text_remote = p_remote + sz_item
        p_pt_remote = p_remote + sz_item + text_buf_sz

        item = LVITEMW()
        item.mask = 0x0001  # LVIF_TEXT
        item.pszText = p_text_remote
        item.cchTextMax = 256

        for i in range(count):
            item.iItem = i
            item.iSubItem = 0
            k32.WriteProcessMemory(hproc, p_remote, ctypes.byref(item), sz_item, 0)
            u32.SendMessageW(lv, LVM_GETITEMTEXTW, i, p_remote)

            buf = ctypes.create_unicode_buffer(256)
            k32.ReadProcessMemory(hproc, p_text_remote, ctypes.byref(buf), 512, 0)
            name = buf.value.strip()

            pt = POINT()
            u32.SendMessageW(lv, LVM_GETITEMPOSITION, i, p_pt_remote)
            k32.ReadProcessMemory(hproc, p_pt_remote, ctypes.byref(pt), pt_sz, 0)

            # Icon center is roughly offset by 32px horizontally and 24px vertically from origin
            center_x = pt.x + 36
            center_y = pt.y + 36

            if name:
                icons.append({
                    "index": i,
                    "name": name,
                    "x": center_x,
                    "y": center_y,
                    "origin_x": pt.x,
                    "origin_y": pt.y
                })

        k32.VirtualFreeEx(hproc, p_remote, 0, 0x8000)
    finally:
        k32.CloseHandle(hproc)

    return icons

def find_desktop_icon(query):
    """Finds first desktop icon matching query substring."""
    query_lower = query.lower()
    icons = get_desktop_icons()

    # Exact match first
    for ic in icons:
        if ic["name"].lower() == query_lower:
            return ic

    # Substring match
    for ic in icons:
        if query_lower in ic["name"].lower():
            return ic

    return None

def launch_desktop_icon(query):
    """
    Instantly locates icon on desktop, shows desktop, moves cursor, and double clicks.
    Takes under 0.5s end-to-end!
    """
    ic = find_desktop_icon(query)
    if not ic:
        raise ValueError(f"Desktop icon matching '{query}' not found")

    import mouse
    import keyboard
    import overlay

    # Start visual overlay
    overlay.start_overlay(duration=2.5)

    # Show desktop Win+D
    keyboard.hotkey('win', 'd')
    time.sleep(0.15)

    # Move cursor smoothly to icon and double click
    mouse.move(ic["x"], ic["y"], smooth=True, duration=0.15)
    time.sleep(0.05)
    mouse.click(ic["x"], ic["y"], button="left", count=2)

    return {
        "action": "launch_desktop_icon",
        "icon": ic["name"],
        "x": ic["x"],
        "y": ic["y"],
        "status": "launched"
    }

def main():
    common_parser = argparse.ArgumentParser(add_help=False)
    common_parser.add_argument("--json", action="store_true")

    parser = argparse.ArgumentParser(
        description="Desktop Icon Fast Locator & Launcher",
        parents=[common_parser]
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list", parents=[common_parser], help="List all desktop icons with coordinates")

    p_find = subparsers.add_parser("find", parents=[common_parser], help="Find desktop icon coordinates by name")
    p_find.add_argument("name", help="Icon name substring")

    p_launch = subparsers.add_parser("launch", parents=[common_parser], help="Instantly find and launch desktop icon")
    p_launch.add_argument("name", help="Icon name substring")

    args = parser.parse_args()

    try:
        cmd = args.command
        res = None

        if cmd == "list":
            res = get_desktop_icons()
        elif cmd == "find":
            res = find_desktop_icon(args.name)
            if not res:
                raise ValueError(f"No desktop icon matching '{args.name}' found")
        elif cmd == "launch":
            res = launch_desktop_icon(args.name)

        if args.json:
            print(json.dumps(res))
        else:
            if cmd == "list":
                print(f"Desktop Icons ({len(res)} found):")
                for item in res:
                    print(f"  - '{item['name']}' at ({item['x']}, {item['y']})")
            elif cmd == "find":
                print(f"Found '{res['name']}' at physical coordinates X={res['x']}, Y={res['y']}")
            elif cmd == "launch":
                print(f"Launched '{res['icon']}' at ({res['x']}, {res['y']})")

    except Exception as e:
        if args.json:
            print(json.dumps({"error": str(e)}))
        else:
            print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()

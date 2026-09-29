"""
Mouse Control Module for Computer Use
Provides precise, DPI-aware mouse automation on Windows.
Supports move, click, double/triple click, drag, scroll, and position inspection.
"""

import sys
import time
import argparse
import ctypes
import json

u32 = ctypes.windll.user32

# Flags
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_WHEEL = 0x0800
MOUSEEVENTF_HWHEEL = 0x1000
MOUSEEVENTF_ABSOLUTE = 0x8000

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

class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

def get_position():
    init_dpi()
    attach_input_desktop()
    pt = POINT()
    u32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y

def get_screen_size():
    init_dpi()
    attach_input_desktop()
    return u32.GetSystemMetrics(0), u32.GetSystemMetrics(1)

def check_failsafe():
    x, y = get_position()
    if x <= 1 and y <= 1:
        raise RuntimeError("Fail-safe triggered: mouse cursor moved to corner (0,0)")

def move(x, y, smooth=False, duration=0.2):
    init_dpi()
    attach_input_desktop()
    x = int(round(x))
    y = int(round(y))

    if not smooth:
        u32.SetCursorPos(x, y)
        return x, y

    cur_x, cur_y = get_position()
    steps = max(5, int(duration * 60))
    dt = duration / steps
    for i in range(1, steps + 1):
        t = i / steps
        # Smooth ease-in-out curve
        t_smooth = t * t * (3 - 2 * t)
        nx = int(round(cur_x + (x - cur_x) * t_smooth))
        ny = int(round(cur_y + (y - cur_y) * t_smooth))
        u32.SetCursorPos(nx, ny)
        time.sleep(dt)

    u32.SetCursorPos(x, y)
    return x, y

def mouse_down(button='left'):
    init_dpi()
    attach_input_desktop()
    btn = button.lower()
    if btn in ('left', 'l'):
        u32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    elif btn in ('right', 'r'):
        u32.mouse_event(MOUSEEVENTF_RIGHTDOWN, 0, 0, 0, 0)
    elif btn in ('middle', 'm'):
        u32.mouse_event(MOUSEEVENTF_MIDDLEDOWN, 0, 0, 0, 0)
    else:
        raise ValueError(f"Unsupported mouse button: {button}")

def mouse_up(button='left'):
    init_dpi()
    attach_input_desktop()
    btn = button.lower()
    if btn in ('left', 'l'):
        u32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
    elif btn in ('right', 'r'):
        u32.mouse_event(MOUSEEVENTF_RIGHTUP, 0, 0, 0, 0)
    elif btn in ('middle', 'm'):
        u32.mouse_event(MOUSEEVENTF_MIDDLEUP, 0, 0, 0, 0)
    else:
        raise ValueError(f"Unsupported mouse button: {button}")

def click(x=None, y=None, button='left', count=1, delay=0.04):
    init_dpi()
    attach_input_desktop()
    if x is not None and y is not None:
        move(x, y)
        time.sleep(0.04)

    for i in range(count):
        mouse_down(button)
        time.sleep(delay)
        mouse_up(button)
        if i < count - 1:
            time.sleep(0.08)

    cur_x, cur_y = get_position()
    return {"action": "click", "x": cur_x, "y": cur_y, "button": button, "count": count}

def drag(start_x, start_y, end_x, end_y, duration=0.3, button='left'):
    init_dpi()
    attach_input_desktop()
    move(start_x, start_y)
    time.sleep(0.05)
    mouse_down(button)
    time.sleep(0.05)
    move(end_x, end_y, smooth=True, duration=duration)
    time.sleep(0.05)
    mouse_up(button)
    return {"action": "drag", "from": [start_x, start_y], "to": [end_x, end_y], "button": button}

def scroll(clicks, x=None, y=None, horizontal=False):
    init_dpi()
    attach_input_desktop()
    if x is not None and y is not None:
        move(x, y)
        time.sleep(0.04)

    flag = MOUSEEVENTF_HWHEEL if horizontal else MOUSEEVENTF_WHEEL
    delta = int(clicks * 120)
    u32.mouse_event(flag, 0, 0, delta, 0)
    cur_x, cur_y = get_position()
    return {"action": "scroll", "clicks": clicks, "horizontal": horizontal, "at": [cur_x, cur_y]}

def main():
    parser = argparse.ArgumentParser(description="Computer Use Mouse Control")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # pos
    subparsers.add_parser("pos", help="Get cursor position")
    subparsers.add_parser("screen", help="Get screen resolution")

    # move
    p_move = subparsers.add_parser("move", help="Move cursor")
    p_move.add_argument("x", type=int)
    p_move.add_argument("y", type=int)
    p_move.add_argument("--smooth", action="store_true", help="Smooth interpolated movement")
    p_move.add_argument("--duration", type=float, default=0.2, help="Duration for smooth move")

    # click
    p_click = subparsers.add_parser("click", help="Click mouse button")
    p_click.add_argument("x", type=int, nargs="?", default=None)
    p_click.add_argument("y", type=int, nargs="?", default=None)
    p_click.add_argument("--button", choices=["left", "right", "middle"], default="left")
    p_click.add_argument("--count", type=int, default=1)

    # double-click
    p_dbl = subparsers.add_parser("double-click", help="Double click")
    p_dbl.add_argument("x", type=int, nargs="?", default=None)
    p_dbl.add_argument("y", type=int, nargs="?", default=None)

    # right-click
    p_rc = subparsers.add_parser("right-click", help="Right click")
    p_rc.add_argument("x", type=int, nargs="?", default=None)
    p_rc.add_argument("y", type=int, nargs="?", default=None)

    # drag
    p_drag = subparsers.add_parser("drag", help="Drag and drop")
    p_drag.add_argument("x1", type=int)
    p_drag.add_argument("y1", type=int)
    p_drag.add_argument("x2", type=int)
    p_drag.add_argument("y2", type=int)
    p_drag.add_argument("--duration", type=float, default=0.3)
    p_drag.add_argument("--button", choices=["left", "right", "middle"], default="left")

    # scroll
    p_scroll = subparsers.add_parser("scroll", help="Scroll mouse wheel")
    p_scroll.add_argument("clicks", type=float)
    p_scroll.add_argument("--x", type=int, default=None)
    p_scroll.add_argument("--y", type=int, default=None)
    p_scroll.add_argument("--horizontal", action="store_true")

    # mouse down/up
    p_down = subparsers.add_parser("down", help="Press and hold mouse button")
    p_down.add_argument("--button", choices=["left", "right", "middle"], default="left")
    p_up = subparsers.add_parser("up", help="Release mouse button")
    p_up.add_argument("--button", choices=["left", "right", "middle"], default="left")

    parser.add_argument("--json", action="store_true", help="Output JSON result")

    args = parser.parse_args()

    try:
        res = None
        cmd = args.command

        if cmd == "pos":
            x, y = get_position()
            res = {"x": x, "y": y}
        elif cmd == "screen":
            w, h = get_screen_size()
            res = {"width": w, "height": h}
        elif cmd == "move":
            mx, my = move(args.x, args.y, smooth=args.smooth, duration=args.duration)
            res = {"action": "move", "x": mx, "y": my}
        elif cmd == "click":
            res = click(args.x, args.y, button=args.button, count=args.count)
        elif cmd == "double-click":
            res = click(args.x, args.y, button="left", count=2)
        elif cmd == "right-click":
            res = click(args.x, args.y, button="right", count=1)
        elif cmd == "drag":
            res = drag(args.x1, args.y1, args.x2, args.y2, duration=args.duration, button=args.button)
        elif cmd == "scroll":
            res = scroll(args.clicks, x=args.x, y=args.y, horizontal=args.horizontal)
        elif cmd == "down":
            mouse_down(args.button)
            res = {"action": "down", "button": args.button}
        elif cmd == "up":
            mouse_up(args.button)
            res = {"action": "up", "button": args.button}

        if args.json:
            print(json.dumps(res))
        else:
            if cmd == "pos":
                print(f"Cursor position: X={res['x']}, Y={res['y']}")
            elif cmd == "screen":
                print(f"Screen resolution: {res['width']}x{res['height']}")
            else:
                print(f"Done: {res}")

    except Exception as e:
        if args.json:
            print(json.dumps({"error": str(e)}))
        else:
            print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()

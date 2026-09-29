#!/usr/bin/env python3
"""
Unified Computer Use Engine & CLI for Antigravity & Codex
Analog of OpenAI Codex Computer Use & Anthropic Computer Use on Windows.

Provides an agentic observe-decide-act loop with:
- DPI-aware screenshotting with coordinate grid overlays and cursor markers
- Precision mouse control (click, move, drag, scroll)
- Keyboard input (Unicode type, clipboard paste, hotkeys)
- Window management (list, focus, minimize, maximize)
- Clipboard integration
- Batch multi-action execution with fail-safe support
"""

import sys
import os
import time
import argparse
import json

# Ensure scripts dir is on sys.path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

import screen
import mouse
import keyboard
import window
import clipboard
import overlay
import desktop

def execute_action(action_dict):
    """Executes a single action dictionary and returns result."""
    action_type = action_dict.get("action", "").lower().replace("-", "_")

    if action_type in ("screenshot", "screen_shot"):
        path = action_dict.get("path") or action_dict.get("output")
        grid = action_dict.get("grid", False)
        cursor = action_dict.get("cursor", False)
        marker = None
        if "marker_x" in action_dict and "marker_y" in action_dict:
            marker = (action_dict["marker_x"], action_dict["marker_y"])
        crop = action_dict.get("crop")
        return screen.capture_screenshot(
            output_path=path,
            grid=grid,
            cursor=cursor,
            cursor_coords=marker,
            region=crop
        )

    elif action_type in ("click", "left_click"):
        x = action_dict.get("x")
        y = action_dict.get("y")
        btn = action_dict.get("button", "left")
        cnt = action_dict.get("count", 1)
        return mouse.click(x, y, button=btn, count=cnt)

    elif action_type == "double_click":
        x = action_dict.get("x")
        y = action_dict.get("y")
        return mouse.click(x, y, button="left", count=2)

    elif action_type == "triple_click":
        x = action_dict.get("x")
        y = action_dict.get("y")
        return mouse.click(x, y, button="left", count=3)

    elif action_type in ("right_click", "context_menu"):
        x = action_dict.get("x")
        y = action_dict.get("y")
        return mouse.click(x, y, button="right", count=1)

    elif action_type == "middle_click":
        x = action_dict.get("x")
        y = action_dict.get("y")
        return mouse.click(x, y, button="middle", count=1)

    elif action_type in ("move", "mouse_move"):
        x = action_dict["x"]
        y = action_dict["y"]
        smooth = action_dict.get("smooth", False)
        dur = action_dict.get("duration", 0.2)
        mx, my = mouse.move(x, y, smooth=smooth, duration=dur)
        return {"action": "move", "x": mx, "y": my}

    elif action_type in ("drag", "mouse_drag"):
        x1 = action_dict["x1"]
        y1 = action_dict["y1"]
        x2 = action_dict["x2"]
        y2 = action_dict["y2"]
        dur = action_dict.get("duration", 0.3)
        btn = action_dict.get("button", "left")
        return mouse.drag(x1, y1, x2, y2, duration=dur, button=btn)

    elif action_type == "scroll":
        clicks = action_dict.get("clicks", 0)
        x = action_dict.get("x")
        y = action_dict.get("y")
        horiz = action_dict.get("horizontal", False)
        return mouse.scroll(clicks, x=x, y=y, horizontal=horiz)

    elif action_type in ("mouse_down", "down"):
        btn = action_dict.get("button", "left")
        mouse.mouse_down(btn)
        return {"action": "mouse_down", "button": btn}

    elif action_type in ("mouse_up", "up"):
        btn = action_dict.get("button", "left")
        mouse.mouse_up(btn)
        return {"action": "mouse_up", "button": btn}

    elif action_type == "cursor":
        x, y = mouse.get_position()
        return {"cursor": {"x": x, "y": y}}

    elif action_type == "screen_size":
        w, h = mouse.get_screen_size()
        return {"screen": {"width": w, "height": h}}

    elif action_type in ("type", "type_text"):
        txt = action_dict.get("text", "")
        delay = action_dict.get("delay", 0.01)
        if action_dict.get("paste", False):
            return keyboard.paste_text(txt)
        return keyboard.type_text(txt, delay=delay)

    elif action_type in ("paste", "paste_text"):
        txt = action_dict.get("text", "")
        return keyboard.paste_text(txt)

    elif action_type in ("press", "key"):
        k = action_dict.get("key") or action_dict.get("keys")
        return keyboard.press_key(k)

    elif action_type in ("hotkey", "combo"):
        keys = action_dict.get("keys", [])
        if isinstance(keys, str):
            keys = [keys]
        return keyboard.hotkey(*keys)

    elif action_type in ("windows", "list_windows"):
        all_win = action_dict.get("all", False)
        return window.list_windows(include_hidden=all_win)

    elif action_type in ("focus", "focus_window"):
        query = action_dict.get("window") or action_dict.get("query") or action_dict.get("title")
        return window.focus_window(query)

    elif action_type == "minimize":
        query = action_dict.get("window") or action_dict.get("query")
        return window.minimize_window(query)

    elif action_type == "maximize":
        query = action_dict.get("window") or action_dict.get("query")
        return window.maximize_window(query)

    elif action_type == "active_window":
        return window.get_active_window()

    elif action_type == "clipboard":
        sub = action_dict.get("subcommand", "get")
        if sub == "get":
            t = clipboard.get_clipboard_text()
            return {"clipboard": t, "length": len(t)}
        elif sub == "set":
            t = action_dict.get("text", "")
            clipboard.set_clipboard_text(t)
            return {"action": "set_clipboard", "length": len(t)}

    elif action_type in ("wait", "sleep"):
        sec = float(action_dict.get("seconds") or action_dict.get("duration") or 1.0)
        time.sleep(sec)
        return {"action": "wait", "seconds": sec}

    elif action_type in ("desktop_icons", "list_icons"):
        return desktop.get_desktop_icons()

    elif action_type in ("find_icon", "find_desktop_icon"):
        q = action_dict.get("name") or action_dict.get("query")
        return desktop.find_desktop_icon(q)

    elif action_type in ("launch_icon", "launch_desktop_icon"):
        q = action_dict.get("name") or action_dict.get("query")
        return desktop.launch_desktop_icon(q)

    elif action_type == "overlay":
        sub = action_dict.get("subcommand", "start")
        if sub == "start":
            dur = action_dict.get("duration", 5.0)
            pid = overlay.start_overlay(duration=dur)
            return {"action": "overlay_start", "pid": pid}
        elif sub == "stop":
            stopped = overlay.stop_overlay()
            return {"action": "overlay_stop", "stopped": stopped}

    else:
        raise ValueError(f"Unknown action: '{action_type}'")

def run_batch(actions_data):
    """Executes a sequential list of actions with failsafe checks and active visual overlay."""
    if isinstance(actions_data, str):
        if os.path.exists(actions_data):
            with open(actions_data, "r", encoding="utf-8") as f:
                actions = json.load(f)
        else:
            actions = json.loads(actions_data)
    else:
        actions = actions_data

    # Turn on visual overlay during batch execution
    overlay.start_overlay(duration=30.0)

    results = []
    try:
        for i, act in enumerate(actions):
            mouse.check_failsafe()
            try:
                res = execute_action(act)
                results.append({"step": i, "status": "ok", "result": res})
            except Exception as e:
                results.append({"step": i, "status": "error", "error": str(e)})
                break
    finally:
        overlay.stop_overlay()

    return results

def main():
    common_parser = argparse.ArgumentParser(add_help=False)
    common_parser.add_argument("--json", action="store_true", help="Output result in JSON format")

    parser = argparse.ArgumentParser(
        description="Computer Use Agent CLI for Windows (Codex Analog)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        parents=[common_parser]
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # 1. screenshot
    p_sc = subparsers.add_parser("screenshot", parents=[common_parser], help="Capture desktop screenshot")
    p_sc.add_argument("output", nargs="?", default=None, help="Output PNG path")
    p_sc.add_argument("--grid", action="store_true", help="Draw 100px coordinate grid overlay")
    p_sc.add_argument("--cursor", action="store_true", help="Draw cursor position target marker")
    p_sc.add_argument("--marker-x", type=int, default=None, help="Custom target marker X")
    p_sc.add_argument("--marker-y", type=int, default=None, help="Custom target marker Y")
    p_sc.add_argument("--crop", nargs=4, type=int, metavar=('X', 'Y', 'W', 'H'), help="Crop region")

    # 2. click
    p_clk = subparsers.add_parser("click", parents=[common_parser], help="Click mouse")
    p_clk.add_argument("x", type=int, nargs="?", default=None, help="X coordinate")
    p_clk.add_argument("y", type=int, nargs="?", default=None, help="Y coordinate")
    p_clk.add_argument("--button", choices=["left", "right", "middle"], default="left")
    p_clk.add_argument("--count", type=int, default=1, help="1=single, 2=double, 3=triple")

    # 3. double-click & right-click shortcuts
    p_dc = subparsers.add_parser("double-click", parents=[common_parser], help="Double click at coordinates")
    p_dc.add_argument("x", type=int, nargs="?", default=None)
    p_dc.add_argument("y", type=int, nargs="?", default=None)

    p_rc = subparsers.add_parser("right-click", parents=[common_parser], help="Right click at coordinates")
    p_rc.add_argument("x", type=int, nargs="?", default=None)
    p_rc.add_argument("y", type=int, nargs="?", default=None)

    # 4. move
    p_mv = subparsers.add_parser("move", parents=[common_parser], help="Move mouse cursor")
    p_mv.add_argument("x", type=int, help="X coordinate")
    p_mv.add_argument("y", type=int, help="Y coordinate")
    p_mv.add_argument("--smooth", action="store_true", help="Smooth interpolated move")
    p_mv.add_argument("--duration", type=float, default=0.2, help="Smooth move duration")

    # 5. drag
    p_dg = subparsers.add_parser("drag", parents=[common_parser], help="Drag and drop from (x1, y1) to (x2, y2)")
    p_dg.add_argument("x1", type=int)
    p_dg.add_argument("y1", type=int)
    p_dg.add_argument("x2", type=int)
    p_dg.add_argument("y2", type=int)
    p_dg.add_argument("--duration", type=float, default=0.3)
    p_dg.add_argument("--button", choices=["left", "right", "middle"], default="left")

    # 6. scroll
    p_scrl = subparsers.add_parser("scroll", parents=[common_parser], help="Scroll mouse wheel (+ up, - down)")
    p_scrl.add_argument("clicks", type=float, help="Scroll clicks")
    p_scrl.add_argument("--x", type=int, default=None)
    p_scrl.add_argument("--y", type=int, default=None)
    p_scrl.add_argument("--horizontal", action="store_true")

    # 7. type
    p_tp = subparsers.add_parser("type", parents=[common_parser], help="Type Unicode text")
    p_tp.add_argument("text", help="Text string to type")
    p_tp.add_argument("--delay", type=float, default=0.01, help="Delay between keys")
    p_tp.add_argument("--paste", action="store_true", help="Use fast clipboard paste instead")

    # 8. paste
    p_pst = subparsers.add_parser("paste", parents=[common_parser], help="Paste text instantly via clipboard + Ctrl+V")
    p_pst.add_argument("text", help="Text to paste")

    # 9. press
    p_pr = subparsers.add_parser("press", parents=[common_parser], help="Press single key (enter, esc, tab, space, win, etc.)")
    p_pr.add_argument("key", help="Key name")

    # 10. hotkey
    p_hk = subparsers.add_parser("hotkey", parents=[common_parser], help="Press hotkey combination (e.g. ctrl c, alt tab, win r)")
    p_hk.add_argument("keys", nargs="+", help="Keys in combination")

    # 11. windows & focus
    p_win = subparsers.add_parser("windows", parents=[common_parser], help="List visible desktop windows")
    p_win.add_argument("--all", action="store_true", help="Include hidden windows")

    p_foc = subparsers.add_parser("focus", parents=[common_parser], help="Bring window to front and focus")
    p_foc.add_argument("query", help="Window title substring or process name")

    p_min = subparsers.add_parser("minimize", parents=[common_parser], help="Minimize window")
    p_min.add_argument("query", help="Window title substring or process name")

    p_max = subparsers.add_parser("maximize", parents=[common_parser], help="Maximize window")
    p_max.add_argument("query", help="Window title substring or process name")

    subparsers.add_parser("active-window", parents=[common_parser], help="Get active foreground window info")

    # 12. cursor & screen info
    subparsers.add_parser("cursor", parents=[common_parser], help="Get current mouse cursor position")
    subparsers.add_parser("screen", parents=[common_parser], help="Get screen resolution")

    # 13. clipboard
    p_cb = subparsers.add_parser("clipboard", parents=[common_parser], help="Read or write clipboard")
    p_cb.add_argument("action", choices=["get", "set"])
    p_cb.add_argument("text", nargs="?", default="")

    # 14. wait
    p_wt = subparsers.add_parser("wait", parents=[common_parser], help="Wait for specified seconds")
    p_wt.add_argument("seconds", type=float, help="Seconds to sleep")

    # 15. batch
    p_bt = subparsers.add_parser("batch", parents=[common_parser], help="Run sequence of actions from JSON string or file")
    p_bt.add_argument("actions", help="JSON string or path to JSON file")

    # 16. overlay
    p_ov = subparsers.add_parser("overlay", parents=[common_parser], help="Control visual Google border overlay")
    p_ov.add_argument("action", choices=["start", "stop", "status"])
    p_ov.add_argument("--duration", type=float, default=None)

    # 17. desktop icons
    subparsers.add_parser("desktop-icons", parents=[common_parser], help="List all desktop icons with coordinates")

    p_fi = subparsers.add_parser("find-icon", parents=[common_parser], help="Find desktop icon coordinates by name")
    p_fi.add_argument("name", help="Icon name substring")

    p_li = subparsers.add_parser("launch-icon", parents=[common_parser], help="Fast launch desktop icon")
    p_li.add_argument("name", help="Icon name substring")

    args = parser.parse_args()

    try:
        cmd = args.command
        res = None

        if cmd == "screenshot":
            marker = (args.marker_x, args.marker_y) if (args.marker_x is not None and args.marker_y is not None) else None
            cursor_flag = args.cursor or (marker is not None)
            res = screen.capture_screenshot(
                output_path=args.output,
                grid=args.grid,
                cursor=cursor_flag,
                cursor_coords=marker,
                region=args.crop
            )
        elif cmd == "click":
            res = mouse.click(args.x, args.y, button=args.button, count=args.count)
        elif cmd == "double-click":
            res = mouse.click(args.x, args.y, button="left", count=2)
        elif cmd == "right-click":
            res = mouse.click(args.x, args.y, button="right", count=1)
        elif cmd == "move":
            mx, my = mouse.move(args.x, args.y, smooth=args.smooth, duration=args.duration)
            res = {"action": "move", "x": mx, "y": my}
        elif cmd == "drag":
            res = mouse.drag(args.x1, args.y1, args.x2, args.y2, duration=args.duration, button=args.button)
        elif cmd == "scroll":
            res = mouse.scroll(args.clicks, x=args.x, y=args.y, horizontal=args.horizontal)
        elif cmd == "type":
            if args.paste:
                res = keyboard.paste_text(args.text)
            else:
                res = keyboard.type_text(args.text, delay=args.delay)
        elif cmd == "paste":
            res = keyboard.paste_text(args.text)
        elif cmd == "press":
            res = keyboard.press_key(args.key)
        elif cmd == "hotkey":
            res = keyboard.hotkey(*args.keys)
        elif cmd == "windows":
            res = window.list_windows(include_hidden=args.all)
        elif cmd == "focus":
            res = window.focus_window(args.query)
        elif cmd == "minimize":
            res = window.minimize_window(args.query)
        elif cmd == "maximize":
            res = window.maximize_window(args.query)
        elif cmd == "active-window":
            res = window.get_active_window()
        elif cmd == "cursor":
            x, y = mouse.get_position()
            res = {"x": x, "y": y}
        elif cmd == "screen":
            w, h = mouse.get_screen_size()
            res = {"width": w, "height": h}
        elif cmd == "clipboard":
            if args.action == "get":
                t = clipboard.get_clipboard_text()
                res = {"text": t, "length": len(t)}
            else:
                clipboard.set_clipboard_text(args.text)
                res = {"action": "set", "length": len(args.text)}
        elif cmd == "wait":
            time.sleep(args.seconds)
            res = {"action": "wait", "seconds": args.seconds}
        elif cmd == "batch":
            res = run_batch(args.actions)
        elif cmd == "overlay":
            if args.action == "start":
                pid = overlay.start_overlay(duration=args.duration)
                res = {"action": "overlay_start", "pid": pid}
            elif args.action == "stop":
                stopped = overlay.stop_overlay()
                res = {"action": "overlay_stop", "stopped": stopped}
            elif args.action == "status":
                pid_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "overlay.pid")
                res = {"running": os.path.exists(pid_file)}
        elif cmd == "desktop-icons":
            res = desktop.get_desktop_icons()
        elif cmd == "find-icon":
            res = desktop.find_desktop_icon(args.name)
            if not res:
                raise ValueError(f"Desktop icon '{args.name}' not found")
        elif cmd == "launch-icon":
            res = desktop.launch_desktop_icon(args.name)

        if args.json:
            print(json.dumps(res))
        else:
            if cmd == "screenshot":
                print(f"Screenshot saved: {res['path']} ({res['width']}x{res['height']})")
            elif cmd == "cursor":
                print(f"Cursor: X={res['x']}, Y={res['y']}")
            elif cmd == "screen":
                print(f"Screen: {res['width']}x{res['height']}")
            elif cmd == "windows":
                print(f"Active Desktop Windows ({len(res)} found):")
                for w in res:
                    act = " [ACTIVE]" if w["active"] else ""
                    print(f"[{w['process'] or 'Unknown'}] '{w['title'][:45]}' HWND:{w['hwnd']} Bounds:{w['bounds']}{act}")
            elif cmd == "clipboard" and args.action == "get":
                print(res["text"])
            else:
                print(f"Success: {res}")

    except Exception as e:
        if args.json:
            print(json.dumps({"error": str(e)}))
        else:
            print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()

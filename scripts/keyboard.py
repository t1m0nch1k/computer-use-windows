"""
Keyboard Control Module for Computer Use
Provides Unicode text typing, clipboard-assisted pasting, single key presses,
and multi-key hotkey combinations on Windows.
"""

import sys
import time
import argparse
import ctypes
import json

u32 = ctypes.windll.user32

INPUT_KEYBOARD = 1
KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004

VK_CODES = {
    'backspace': 0x08, 'bs': 0x08,
    'tab': 0x09,
    'clear': 0x0C,
    'enter': 0x0D, 'return': 0x0D,
    'shift': 0x10,
    'ctrl': 0x11, 'control': 0x11,
    'alt': 0x12, 'menu': 0x12,
    'pause': 0x13,
    'capslock': 0x14,
    'esc': 0x1B, 'escape': 0x1B,
    'space': 0x20, 'spacebar': 0x20,
    'pageup': 0x21, 'pgup': 0x21,
    'pagedown': 0x22, 'pgdn': 0x22,
    'end': 0x23,
    'home': 0x24,
    'left': 0x25,
    'up': 0x26,
    'right': 0x27,
    'down': 0x28,
    'select': 0x29,
    'print': 0x2A,
    'execute': 0x2B,
    'prtsc': 0x2C, 'printscreen': 0x2C,
    'insert': 0x2D, 'ins': 0x2D,
    'delete': 0x2E, 'del': 0x2E,
    'help': 0x2F,
    'win': 0x5B, 'super': 0x5B, 'lwin': 0x5B,
    'rwin': 0x5C,
    'apps': 0x5D,
    'sleep': 0x5F,
    'numpad0': 0x60, 'numpad1': 0x61, 'numpad2': 0x62, 'numpad3': 0x63,
    'numpad4': 0x64, 'numpad5': 0x65, 'numpad6': 0x66, 'numpad7': 0x67,
    'numpad8': 0x68, 'numpad9': 0x69,
    'multiply': 0x6A, 'add': 0x6B, 'separator': 0x6C, 'subtract': 0x6D, 'decimal': 0x6E, 'divide': 0x6F,
    'f1': 0x70, 'f2': 0x71, 'f3': 0x72, 'f4': 0x73, 'f5': 0x74, 'f6': 0x75,
    'f7': 0x76, 'f8': 0x77, 'f9': 0x78, 'f10': 0x79, 'f11': 0x7A, 'f12': 0x7B
}

for i in range(10):
    VK_CODES[str(i)] = 0x30 + i
for i in range(26):
    VK_CODES[chr(97 + i)] = 0x41 + i

class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", ctypes.c_ushort),
        ("wScan", ctypes.c_ushort),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))
    ]

class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", ctypes.c_ulong),
        ("wParamL", ctypes.c_short),
        ("wParamH", ctypes.c_ushort)
    ]

class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", ctypes.c_long),
        ("dy", ctypes.c_long),
        ("mouseData", ctypes.c_ulong),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))
    ]

class INPUT(ctypes.Structure):
    class _INPUT(ctypes.Union):
        _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT), ("hi", HARDWAREINPUT)]
    _anonymous_ = ("_input",)
    _fields_ = [("type", ctypes.c_ulong), ("_input", _INPUT)]

def attach_input_desktop():
    try:
        hinput = u32.OpenInputDesktop(0, False, 0x01FF)
        if hinput:
            u32.SetThreadDesktop(hinput)
            return hinput
    except Exception:
        pass
    return None

def send_unicode_char(char):
    """Sends a single unicode character keypress via SendInput."""
    code = ord(char)
    inp_down = INPUT()
    inp_down.type = INPUT_KEYBOARD
    inp_down.ki.wScan = code
    inp_down.ki.dwFlags = KEYEVENTF_UNICODE

    inp_up = INPUT()
    inp_up.type = INPUT_KEYBOARD
    inp_up.ki.wScan = code
    inp_up.ki.dwFlags = KEYEVENTF_UNICODE | KEYEVENTF_KEYUP

    inputs = (INPUT * 2)(inp_down, inp_up)
    u32.SendInput(2, ctypes.byref(inputs), ctypes.sizeof(INPUT))

def type_text(text, delay=0.01):
    """Types out full text string character by character (Unicode aware)."""
    attach_input_desktop()
    for char in text:
        if char == '\n':
            press_key('enter')
        elif char == '\t':
            press_key('tab')
        else:
            send_unicode_char(char)
        if delay > 0:
            time.sleep(delay)
    return {"action": "type", "length": len(text)}

def key_down(vk_code):
    attach_input_desktop()
    u32.keybd_event(vk_code, 0, 0, 0)

def key_up(vk_code):
    attach_input_desktop()
    u32.keybd_event(vk_code, 0, KEYEVENTF_KEYUP, 0)

def press_key(key_name):
    """Presses and releases a single key."""
    attach_input_desktop()
    k = key_name.lower().strip()
    if k in VK_CODES:
        vk = VK_CODES[k]
        key_down(vk)
        time.sleep(0.02)
        key_up(vk)
    else:
        # Fallback to unicode char
        type_text(key_name)
    return {"action": "press", "key": key_name}

def hotkey(*keys):
    """Presses a combination of keys together (e.g. 'ctrl', 'shift', 'esc')."""
    attach_input_desktop()
    vks = []
    # If a single string with '+' was passed, e.g. "ctrl+c"
    expanded_keys = []
    for k in keys:
        if '+' in k:
            expanded_keys.extend(k.split('+'))
        else:
            expanded_keys.append(k)

    for k in expanded_keys:
        k_clean = k.lower().strip()
        if k_clean in VK_CODES:
            vks.append(VK_CODES[k_clean])
        else:
            raise ValueError(f"Unknown key in hotkey: '{k}'")

    for vk in vks:
        key_down(vk)
        time.sleep(0.02)

    time.sleep(0.05)

    for vk in reversed(vks):
        key_up(vk)
        time.sleep(0.02)

    return {"action": "hotkey", "keys": expanded_keys}

def set_clipboard(text):
    """Sets system clipboard text using Win32 API."""
    CF_UNICODETEXT = 13
    GMEM_MOVEABLE = 0x0002

    kernel32 = ctypes.windll.kernel32
    kernel32.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
    kernel32.GlobalAlloc.restype = ctypes.c_void_p
    kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalUnlock.restype = ctypes.c_bool

    u32.OpenClipboard.argtypes = [ctypes.c_void_p]
    u32.OpenClipboard.restype = ctypes.c_bool
    u32.CloseClipboard.argtypes = []
    u32.CloseClipboard.restype = ctypes.c_bool
    u32.EmptyClipboard.argtypes = []
    u32.EmptyClipboard.restype = ctypes.c_bool
    u32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]
    u32.SetClipboardData.restype = ctypes.c_void_p

    if not u32.OpenClipboard(0):
        return
    try:
        u32.EmptyClipboard()
        encoded = (text + '\0').encode('utf-16le')
        h_mem = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(encoded))
        if h_mem:
            ptr = kernel32.GlobalLock(h_mem)
            if ptr:
                ctypes.memmove(ptr, encoded, len(encoded))
                kernel32.GlobalUnlock(h_mem)
                u32.SetClipboardData(CF_UNICODETEXT, h_mem)
    finally:
        u32.CloseClipboard()

def paste_text(text):
    """Fast insertion of text using clipboard and Ctrl+V."""
    attach_input_desktop()
    set_clipboard(text)
    time.sleep(0.05)
    hotkey('ctrl', 'v')
    return {"action": "paste", "length": len(text)}

def main():
    parser = argparse.ArgumentParser(description="Computer Use Keyboard Control")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # type
    p_type = subparsers.add_parser("type", help="Type text character by character")
    p_type.add_argument("text", type=str, help="Text to type")
    p_type.add_argument("--delay", type=float, default=0.01, help="Delay between keys")

    # paste
    p_paste = subparsers.add_parser("paste", help="Paste text via clipboard and Ctrl+V")
    p_paste.add_argument("text", type=str, help="Text to paste")

    # press
    p_press = subparsers.add_parser("press", help="Press single key")
    p_press.add_argument("key", type=str, help="Key name (e.g. enter, esc, tab, space, win)")

    # hotkey
    p_hotkey = subparsers.add_parser("hotkey", help="Press key combination")
    p_hotkey.add_argument("keys", nargs="+", help="Keys in combination (e.g. ctrl c or ctrl+c)")

    parser.add_argument("--json", action="store_true", help="Output JSON result")

    args = parser.parse_args()

    try:
        res = None
        cmd = args.command

        if cmd == "type":
            res = type_text(args.text, delay=args.delay)
        elif cmd == "paste":
            res = paste_text(args.text)
        elif cmd == "press":
            res = press_key(args.key)
        elif cmd == "hotkey":
            res = hotkey(*args.keys)

        if args.json:
            print(json.dumps(res))
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

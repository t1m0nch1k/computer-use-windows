"""
Clipboard Module for Computer Use
Provides reliable Unicode clipboard read/write operations via Win32 API.
"""

import sys
import argparse
import ctypes
from win_desktop import attach_input_desktop
import json

u32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002

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
u32.GetClipboardData.argtypes = [ctypes.c_uint]
u32.GetClipboardData.restype = ctypes.c_void_p

def get_clipboard_text():
    attach_input_desktop()
    if not u32.OpenClipboard(0):
        return ""
    try:
        h_mem = u32.GetClipboardData(CF_UNICODETEXT)
        if not h_mem:
            return ""
        ptr = kernel32.GlobalLock(h_mem)
        if not ptr:
            return ""
        try:
            return ctypes.wstring_at(ptr)
        finally:
            kernel32.GlobalUnlock(h_mem)
    finally:
        u32.CloseClipboard()

def set_clipboard_text(text):
    attach_input_desktop()
    if not u32.OpenClipboard(0):
        raise RuntimeError("Failed to open clipboard")
    try:
        u32.EmptyClipboard()
        encoded = (text + '\0').encode('utf-16le')
        h_mem = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(encoded))
        if not h_mem:
            raise RuntimeError("GlobalAlloc failed")
        ptr = kernel32.GlobalLock(h_mem)
        if not ptr:
            raise RuntimeError("GlobalLock failed")
        ctypes.memmove(ptr, encoded, len(encoded))
        kernel32.GlobalUnlock(h_mem)
        u32.SetClipboardData(CF_UNICODETEXT, h_mem)
    finally:
        u32.CloseClipboard()
    return len(text)

def main():
    parser = argparse.ArgumentParser(description="Computer Use Clipboard Control")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # get
    subparsers.add_parser("get", help="Get clipboard text")

    # set
    p_set = subparsers.add_parser("set", help="Set clipboard text")
    p_set.add_argument("text", help="Text to copy to clipboard")

    parser.add_argument("--json", action="store_true", help="Output JSON result")

    args = parser.parse_args()

    try:
        res = None
        cmd = args.command

        if cmd == "get":
            text = get_clipboard_text()
            res = {"text": text, "length": len(text)}
        elif cmd == "set":
            count = set_clipboard_text(args.text)
            res = {"action": "set", "length": count}

        if args.json:
            print(json.dumps(res))
        else:
            if cmd == "get":
                print(res["text"])
            else:
                print(f"Copied {res['length']} characters to clipboard.")

    except Exception as e:
        if args.json:
            print(json.dumps({"error": str(e)}))
        else:
            print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()

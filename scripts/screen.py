"""
Screen Capture Module for Computer Use
Provides high-fidelity, DPI-aware desktop screenshot capture on Windows
with optional coordinate grid overlay, cursor visualization, and cropping.
"""

import sys
import os
import argparse
import ctypes
from win_desktop import attach_input_desktop
from win_desktop import init_dpi
from ctypes import wintypes
import capture_store
try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

u32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32

# Pointer-sized handles must not use ctypes' default 32-bit return type.
u32.GetDC.argtypes = [wintypes.HWND]
u32.GetDC.restype = wintypes.HDC
u32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
u32.OpenInputDesktop.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
u32.OpenInputDesktop.restype = wintypes.HANDLE
u32.SetThreadDesktop.argtypes = [wintypes.HANDLE]
u32.CloseDesktop.argtypes = [wintypes.HANDLE]
gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
gdi32.CreateCompatibleDC.restype = wintypes.HDC
gdi32.CreateCompatibleBitmap.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int]
gdi32.CreateCompatibleBitmap.restype = wintypes.HBITMAP
gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HANDLE]
gdi32.SelectObject.restype = wintypes.HANDLE
gdi32.DeleteObject.argtypes = [wintypes.HANDLE]
gdi32.DeleteDC.argtypes = [wintypes.HDC]
gdi32.BitBlt.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                       ctypes.c_int, wintypes.HDC, ctypes.c_int, ctypes.c_int, wintypes.DWORD]
gdi32.GetDIBits.argtypes = [wintypes.HDC, wintypes.HBITMAP, wintypes.UINT,
                          wintypes.UINT, ctypes.c_void_p, ctypes.c_void_p, wintypes.UINT]

class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ('biSize', ctypes.c_uint32),
        ('biWidth', ctypes.c_int32),
        ('biHeight', ctypes.c_int32),
        ('biPlanes', ctypes.c_uint16),
        ('biBitCount', ctypes.c_uint16),
        ('biCompression', ctypes.c_uint32),
        ('biSizeImage', ctypes.c_uint32),
        ('biXPelsPerMeter', ctypes.c_int32),
        ('biYPelsPerMeter', ctypes.c_int32),
        ('biClrUsed', ctypes.c_uint32),
        ('biClrImportant', ctypes.c_uint32)
    ]

class BITMAPINFO(ctypes.Structure):
    _fields_ = [('bmiHeader', BITMAPINFOHEADER), ('bmiColors', ctypes.c_uint32 * 3)]

def get_screen_metrics():
    init_dpi()
    attach_input_desktop()
    w = u32.GetSystemMetrics(0)
    h = u32.GetSystemMetrics(1)
    return w, h

def get_cursor_pos():
    class POINT(ctypes.Structure):
        _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
    pt = POINT()
    u32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y

def capture_screen_raw(region=None):
    """
    Captures screen using direct GDI BitBlt.
    region: (x, y, w, h) or None for full primary monitor.
    Returns a PIL.Image in RGB mode.
    """
    init_dpi()
    attach_input_desktop()

    screen_w = u32.GetSystemMetrics(0)
    screen_h = u32.GetSystemMetrics(1)

    if region:
        rx, ry, rw, rh = region
        rx = max(0, min(rx, screen_w - 1))
        ry = max(0, min(ry, screen_h - 1))
        rw = max(1, min(rw, screen_w - rx))
        rh = max(1, min(rh, screen_h - ry))
    else:
        rx, ry, rw, rh = 0, 0, screen_w, screen_h

    hdc_screen = u32.GetDC(0)
    if not hdc_screen:
        raise RuntimeError("Failed to obtain Screen DC")

    hdc_mem = hbmp = old_bmp = None
    try:
        hdc_mem = gdi32.CreateCompatibleDC(hdc_screen)
        hbmp = gdi32.CreateCompatibleBitmap(hdc_screen, rw, rh)
        if not hdc_mem or not hbmp:
            raise RuntimeError("Failed to allocate capture bitmap")
        old_bmp = gdi32.SelectObject(hdc_mem, hbmp)
        if not gdi32.BitBlt(hdc_mem, 0, 0, rw, rh, hdc_screen, rx, ry, 0x00CC0020):
            raise RuntimeError("BitBlt failed")
        gdi32.SelectObject(hdc_mem, old_bmp)
        old_bmp = None
        bmi = BITMAPINFO()
        bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.bmiHeader.biWidth = rw
        bmi.bmiHeader.biHeight = -rh
        bmi.bmiHeader.biPlanes = 1
        bmi.bmiHeader.biBitCount = 32
        buf = ctypes.create_string_buffer(rw * rh * 4)
        if gdi32.GetDIBits(hdc_mem, hbmp, 0, rh, buf, ctypes.byref(bmi), 0) != rh:
            raise RuntimeError("GetDIBits failed")
        return Image.frombytes('RGB', (rw, rh), buf.raw, 'raw', 'BGRX')
    finally:
        if old_bmp:
            gdi32.SelectObject(hdc_mem, old_bmp)
        if hbmp:
            gdi32.DeleteObject(hbmp)
        if hdc_mem:
            gdi32.DeleteDC(hdc_mem)
        u32.ReleaseDC(0, hdc_screen)


def draw_grid_overlay(img, step=100, origin=(0, 0)):
    """
    Draws coordinate lines and pixel labels over the image.
    Essential for vision models to estimate (X, Y) click coordinates reliably.
    """
    w, h = img.size
    overlay = img
    draw = ImageDraw.Draw(overlay)

    try:
        font = ImageFont.load_default()
    except Exception:
        font = None

    line_color = (0, 200, 255)            # Cyan
    major_line_color = (255, 60, 60)      # Red for 500px marks
    text_color = (255, 255, 0)            # Bright yellow

    # Draw vertical grid lines & X labels
    for x in range((-origin[0]) % step, w, step):
        is_major = ((x + origin[0]) % 500 == 0)
        col = major_line_color if is_major else line_color
        draw.line([(x, 0), (x, h)], fill=col, width=2 if is_major else 1)

        label = f"{x + origin[0]}"
        # Top label
        bbox = draw.textbbox((x + 2, 2), label, font=font)
        draw.rectangle([bbox[0] - 1, bbox[1] - 1, bbox[2] + 1, bbox[3] + 1], fill=(0, 0, 0))
        draw.text((x + 2, 2), label, fill=text_color, font=font)

        # Bottom label
        bbox_bot = draw.textbbox((x + 2, h - 14), label, font=font)
        draw.rectangle([bbox_bot[0] - 1, bbox_bot[1] - 1, bbox_bot[2] + 1, bbox_bot[3] + 1], fill=(0, 0, 0))
        draw.text((x + 2, h - 14), label, fill=text_color, font=font)

    # Draw horizontal grid lines & Y labels
    for y in range((-origin[1]) % step, h, step):
        is_major = ((y + origin[1]) % 500 == 0)
        col = major_line_color if is_major else line_color
        draw.line([(0, y), (w, y)], fill=col, width=2 if is_major else 1)

        label = f"{y + origin[1]}"
        # Left label
        bbox = draw.textbbox((2, y + 2), label, font=font)
        draw.rectangle([bbox[0] - 1, bbox[1] - 1, bbox[2] + 1, bbox[3] + 1], fill=(0, 0, 0))
        draw.text((2, y + 2), label, fill=text_color, font=font)

        # Right label
        bbox_right = draw.textbbox((w - 36, y + 2), label, font=font)
        draw.rectangle([bbox_right[0] - 1, bbox_right[1] - 1, bbox_right[2] + 1, bbox_right[3] + 1], fill=(0, 0, 0))
        draw.text((w - 36, y + 2), label, fill=text_color, font=font)

    return overlay

def draw_cursor_marker(img, cx=None, cy=None, origin=(0, 0)):
    """Draws a crosshair and circular target marker at cursor coordinates."""
    if cx is None or cy is None:
        cx, cy = get_cursor_pos()

    label_coords = (cx, cy)
    cx, cy = cx - origin[0], cy - origin[1]
    w, h = img.size
    overlay = img
    draw = ImageDraw.Draw(overlay)

    r = 14
    # Outer black ring for contrast
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(0, 0, 0), width=3)
    # Inner red ring
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(255, 0, 0), width=2)

    # Crosshairs
    draw.line([(cx - r - 6, cy), (cx + r + 6, cy)], fill=(255, 0, 0), width=2)
    draw.line([(cx, cy - r - 6), (cx, cy + r + 6)], fill=(255, 0, 0), width=2)

    # Center dot
    draw.ellipse([cx - 2, cy - 2, cx + 2, cy + 2], fill=(255, 255, 255))

    # Badge with exact coordinates
    coord_text = f"({label_coords[0]},{label_coords[1]})"
    try:
        font = ImageFont.load_default()
        bbox = draw.textbbox((cx + 12, cy + 12), coord_text, font=font)
        draw.rectangle([bbox[0] - 2, bbox[1] - 2, bbox[2] + 2, bbox[3] + 2], fill=(0, 0, 0))
        draw.text((cx + 12, cy + 12), coord_text, fill=(255, 255, 0), font=font)
    except Exception:
        pass

    return overlay

def capture_screenshot(output_path=None, grid=False, cursor=False, cursor_coords=None,
                       region=None, keep=False):
    """Temporary by default; persistent paths require an explicit keep opt-in."""
    if not HAS_PIL:
        raise RuntimeError("Pillow is required: pip install -r requirements.txt")
    if output_path and not keep:
        raise ValueError("Explicit output paths require --keep; omit the path for a temporary capture")
    if keep and not output_path:
        raise ValueError("--keep requires an explicit output path")
    sw, sh = get_screen_metrics()
    if region:
        if len(region) != 4 or region[2] <= 0 or region[3] <= 0:
            raise ValueError("Crop must contain X Y and positive width/height")
        x, y, w, h = map(int, region)
        x, y = max(0, min(x, sw-1)), max(0, min(y, sh-1))
        region = (x, y, min(w, sw-x), min(h, sh-y))
    origin = region[:2] if region else (0, 0)
    target = os.path.abspath(output_path) if keep else str(capture_store.allocate())
    try:
        os.makedirs(os.path.dirname(target), exist_ok=True)
        img = capture_screen_raw(region=region)
        w, h = img.size
        if grid:
            draw_grid_overlay(img, origin=origin)
        if cursor or cursor_coords:
            cx, cy = cursor_coords if cursor_coords else get_cursor_pos()
            draw_cursor_marker(img, cx, cy, origin=origin)
        # PNG optimization costs CPU and brings little benefit for short-lived captures.
        img.save(target, format="PNG", optimize=False, compress_level=1)
        if not keep:
            capture_store.expire_later(target)
    except BaseException:
        if not keep:
            capture_store.release(target)
        raise
    return {"path": target, "width": w, "height": h, "origin": list(origin),
            "grid": grid, "cursor": bool(cursor or cursor_coords),
            "temporary": not keep, "expires_in_seconds": None if keep else capture_store.TTL}


def main():
    parser = argparse.ArgumentParser(description="Computer Use Screen Capture")
    parser.add_argument("output", nargs="?", default=None, help="Output PNG file path")
    parser.add_argument("--keep", action="store_true", help="Keep explicit output as a user-requested deliverable")
    parser.add_argument("--grid", action="store_true", help="Overlay coordinate grid")
    parser.add_argument("--cursor", action="store_true", help="Draw current mouse cursor position")
    parser.add_argument("--marker-x", type=int, default=None, help="Custom marker X coordinate")
    parser.add_argument("--marker-y", type=int, default=None, help="Custom marker Y coordinate")
    parser.add_argument("--crop", nargs=4, type=int, metavar=('X', 'Y', 'W', 'H'), help="Crop bounding box")
    parser.add_argument("--json", action="store_true", help="Output JSON result")

    args = parser.parse_args()

    cursor_coords = (args.marker_x, args.marker_y) if (args.marker_x is not None and args.marker_y is not None) else None
    cursor_flag = args.cursor or (cursor_coords is not None)

    try:
        res = capture_screenshot(
            output_path=args.output,
            grid=args.grid,
            cursor=cursor_flag,
            cursor_coords=cursor_coords,
            region=args.crop, keep=args.keep
        )
        if args.json:
            import json
            print(json.dumps(res))
        else:
            print(f"Screenshot saved: {res['path']} ({res['width']}x{res['height']})")
    except Exception as e:
        if args.json:
            import json
            print(json.dumps({"error": str(e)}))
        else:
            print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()

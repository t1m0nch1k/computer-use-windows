"""
Screen Capture Module for Computer Use
Provides high-fidelity, DPI-aware desktop screenshot capture on Windows
with optional coordinate grid overlay, cursor visualization, and cropping.
"""

import sys
import os
import time
import argparse
import ctypes
try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

u32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
gp = ctypes.windll.gdiplus

def save_bitmap_gdiplus(hbmp, output_path):
    class GdiplusStartupInput(ctypes.Structure):
        _fields_ = [('GdiplusVersion', ctypes.c_uint32), ('DebugEventCallback', ctypes.c_void_p), ('SuppressBackgroundThread', ctypes.c_bool), ('SuppressExternalCodecs', ctypes.c_bool)]
    class GUID(ctypes.Structure):
        _fields_ = [('Data1', ctypes.c_ulong), ('Data2', ctypes.c_ushort), ('Data3', ctypes.c_ushort), ('Data4', ctypes.c_ubyte * 8)]

    token = ctypes.c_void_p()
    inp = GdiplusStartupInput(1, None, False, False)
    gp.GdiplusStartup(ctypes.byref(token), ctypes.byref(inp), None)
    try:
        p_image = ctypes.c_void_p()
        gp.GdipCreateBitmapFromHBITMAP(hbmp, 0, ctypes.byref(p_image))
        png_clsid = GUID(0x557cf406, 0x1a04, 0x11d3, (ctypes.c_ubyte * 8)(0x9a, 0x73, 0x00, 0x00, 0xf8, 0x1e, 0xf3, 0x2e))
        gp.GdipSaveImageToFile(p_image, output_path, ctypes.byref(png_clsid), None)
        gp.GdipDisposeImage(p_image)
    finally:
        gp.GdiplusShutdown(token)

# Set DPI awareness for 1:1 physical pixel matching
def init_dpi():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PROCESS_PER_MONITOR_DPI_AWARE
    except Exception:
        try:
            u32.SetProcessDPIAware()
        except Exception:
            pass

def attach_input_desktop():
    """Attaches current thread to user's interactive desktop if needed."""
    try:
        hinput = u32.OpenInputDesktop(0, False, 0x01FF)
        if hinput:
            u32.SetThreadDesktop(hinput)
            return hinput
    except Exception:
        pass
    return None

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

    hdc_mem = gdi32.CreateCompatibleDC(hdc_screen)
    hbmp = gdi32.CreateCompatibleBitmap(hdc_screen, rw, rh)
    old_bmp = gdi32.SelectObject(hdc_mem, hbmp)

    # Copy screen bits
    gdi32.BitBlt(hdc_mem, 0, 0, rw, rh, hdc_screen, rx, ry, 0x00CC0020)  # SRCCOPY

    bmi = BITMAPINFO()
    bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bmi.bmiHeader.biWidth = rw
    bmi.bmiHeader.biHeight = -rh  # Top-down DIB
    bmi.bmiHeader.biPlanes = 1
    bmi.bmiHeader.biBitCount = 32
    bmi.bmiHeader.biCompression = 0  # BI_RGB

    buf = ctypes.create_string_buffer(rw * rh * 4)
    gdi32.GetDIBits(hdc_mem, hbmp, 0, rh, buf, ctypes.byref(bmi), 0)

    img = None
    if HAS_PIL:
        img = Image.frombuffer('RGBA', (rw, rh), buf, 'raw', 'BGRA', 0, 1).convert('RGB')
        gdi32.SelectObject(hdc_mem, old_bmp)
        gdi32.DeleteObject(hbmp)
        gdi32.DeleteDC(hdc_mem)
        u32.ReleaseDC(0, hdc_screen)
        return img
    else:
        # Fallback return hbmp and dims
        gdi32.SelectObject(hdc_mem, old_bmp)
        gdi32.DeleteDC(hdc_mem)
        u32.ReleaseDC(0, hdc_screen)
        return hbmp, rw, rh

def draw_grid_overlay(img, step=100):
    """
    Draws coordinate lines and pixel labels over the image.
    Essential for vision models to estimate (X, Y) click coordinates reliably.
    """
    w, h = img.size
    overlay = img.copy()
    draw = ImageDraw.Draw(overlay)

    try:
        font = ImageFont.load_default()
    except Exception:
        font = None

    line_color = (0, 200, 255)            # Cyan
    major_line_color = (255, 60, 60)      # Red for 500px marks
    text_color = (255, 255, 0)            # Bright yellow

    # Draw vertical grid lines & X labels
    for x in range(0, w, step):
        is_major = (x % 500 == 0) and (x > 0)
        col = major_line_color if is_major else line_color
        draw.line([(x, 0), (x, h)], fill=col, width=2 if is_major else 1)

        label = f"{x}"
        # Top label
        bbox = draw.textbbox((x + 2, 2), label, font=font)
        draw.rectangle([bbox[0] - 1, bbox[1] - 1, bbox[2] + 1, bbox[3] + 1], fill=(0, 0, 0))
        draw.text((x + 2, 2), label, fill=text_color, font=font)

        # Bottom label
        bbox_bot = draw.textbbox((x + 2, h - 14), label, font=font)
        draw.rectangle([bbox_bot[0] - 1, bbox_bot[1] - 1, bbox_bot[2] + 1, bbox_bot[3] + 1], fill=(0, 0, 0))
        draw.text((x + 2, h - 14), label, fill=text_color, font=font)

    # Draw horizontal grid lines & Y labels
    for y in range(0, h, step):
        is_major = (y % 500 == 0) and (y > 0)
        col = major_line_color if is_major else line_color
        draw.line([(0, y), (w, y)], fill=col, width=2 if is_major else 1)

        label = f"{y}"
        # Left label
        bbox = draw.textbbox((2, y + 2), label, font=font)
        draw.rectangle([bbox[0] - 1, bbox[1] - 1, bbox[2] + 1, bbox[3] + 1], fill=(0, 0, 0))
        draw.text((2, y + 2), label, fill=text_color, font=font)

        # Right label
        bbox_right = draw.textbbox((w - 36, y + 2), label, font=font)
        draw.rectangle([bbox_right[0] - 1, bbox_right[1] - 1, bbox_right[2] + 1, bbox_right[3] + 1], fill=(0, 0, 0))
        draw.text((w - 36, y + 2), label, fill=text_color, font=font)

    return overlay

def draw_cursor_marker(img, cx=None, cy=None):
    """Draws a crosshair and circular target marker at cursor coordinates."""
    if cx is None or cy is None:
        cx, cy = get_cursor_pos()

    w, h = img.size
    overlay = img.copy()
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
    coord_text = f"({cx},{cy})"
    try:
        font = ImageFont.load_default()
        bbox = draw.textbbox((cx + 12, cy + 12), coord_text, font=font)
        draw.rectangle([bbox[0] - 2, bbox[1] - 2, bbox[2] + 2, bbox[3] + 2], fill=(0, 0, 0))
        draw.text((cx + 12, cy + 12), coord_text, fill=(255, 255, 0), font=font)
    except Exception:
        pass

    return overlay

def capture_screenshot(output_path=None, grid=False, cursor=False, cursor_coords=None, region=None):
    """High-level capture function returning saved file path and image metadata."""
    if not output_path:
        timestamp = int(time.time() * 1000)
        output_path = os.path.abspath(f"screenshot_{timestamp}.png")
    else:
        output_path = os.path.abspath(output_path)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    raw = capture_screen_raw(region=region)

    if HAS_PIL:
        img = raw
        w, h = img.size

        if grid:
            img = draw_grid_overlay(img, step=100)

        if cursor:
            cx, cy = cursor_coords if cursor_coords else (None, None)
            img = draw_cursor_marker(img, cx=cx, cy=cy)

        img.save(output_path, format="PNG", optimize=True)
    else:
        hbmp, w, h = raw
        try:
            save_bitmap_gdiplus(hbmp, output_path)
        finally:
            gdi32.DeleteObject(hbmp)

    return {
        "path": output_path,
        "width": w,
        "height": h,
        "grid": grid if HAS_PIL else False,
        "cursor": cursor if HAS_PIL else False
    }

def main():
    parser = argparse.ArgumentParser(description="Computer Use Screen Capture")
    parser.add_argument("output", nargs="?", default=None, help="Output PNG file path")
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
            region=args.crop
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

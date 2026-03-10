#!/usr/bin/env python3
"""iOS Simulator interaction helper. All coordinates are in device POINTS.

Usage:
  python3 sim_helper.py tap <x> <y>                 - Tap at device point coordinates
  python3 sim_helper.py long_press <x> <y> [secs]   - Long press (context menu) via CGEvent
  python3 sim_helper.py swipe_back                   - iOS swipe-back gesture
  python3 sim_helper.py swipe_up                     - Scroll down (swipe up)
  python3 sim_helper.py swipe_down                   - Scroll up (swipe down)
  python3 sim_helper.py type <text>                  - Type text into focused field
  python3 sim_helper.py screenshot [path]            - Screenshot with coordinate grid overlay
  python3 sim_helper.py info                         - Show booted device info and dimensions

Requires: pyobjc-framework-Quartz, Pillow (for screenshots only), idb (fb-idb)
Install:  pip3 install --break-system-packages pyobjc-framework-Quartz Pillow
          brew install idb-companion && pip3 install --break-system-packages fb-idb
"""
import json
import subprocess
import sys
import time

# ── Device detection ──────────────────────────────────────────────────────────

# Known device point dimensions (logical points, NOT pixels)
KNOWN_DEVICES = {
    "iPhone 13 mini":     (375, 812),
    "iPhone 14":          (390, 844),
    "iPhone 15":          (393, 852),
    "iPhone 15 Pro":      (393, 852),
    "iPhone 15 Pro Max":  (430, 932),
    "iPhone 16":          (393, 852),
    "iPhone 16 Plus":     (430, 932),
    "iPhone 16 Pro":      (402, 874),
    "iPhone 16 Pro Max":  (440, 956),
    "iPhone 16e":         (375, 812),
}

_cached_device = None

def get_booted_device():
    """Auto-detect booted simulator UDID, name, and point dimensions."""
    global _cached_device
    if _cached_device:
        return _cached_device
    result = subprocess.run(
        ["xcrun", "simctl", "list", "devices", "booted", "-j"],
        capture_output=True, text=True
    )
    data = json.loads(result.stdout)
    for runtime, devices in data.get("devices", {}).items():
        for d in devices:
            if d.get("state") == "Booted":
                name = d["name"]
                udid = d["udid"]
                w, h = KNOWN_DEVICES.get(name, (393, 852))  # default to iPhone 16
                _cached_device = {"udid": udid, "name": name, "w": w, "h": h}
                return _cached_device
    print("ERROR: No booted simulator found")
    sys.exit(1)

def device_w():
    return get_booted_device()["w"]

def device_h():
    return get_booted_device()["h"]

# ── Coordinate helpers ────────────────────────────────────────────────────────

def get_window_bounds():
    result = subprocess.run(
        ["osascript", "-e",
         'tell application "System Events" to tell process "Simulator" to get {position, size} of window 1'],
        capture_output=True, text=True
    )
    parts = [int(x.strip()) for x in result.stdout.strip().split(",")]
    return parts[0], parts[1], parts[2], parts[3]  # x, y, w, h

def dev_to_mac(dev_x, dev_y):
    """Convert device point coordinates to macOS screen coordinates."""
    wx, wy, ww, wh = get_window_bounds()
    mac_x = wx + (dev_x / device_w()) * ww
    mac_y = wy + (dev_y / device_h()) * wh
    return mac_x, mac_y

def focus_sim():
    subprocess.run(["osascript", "-e", 'tell application "Simulator" to activate'], capture_output=True)
    time.sleep(0.3)

# ── Actions ───────────────────────────────────────────────────────────────────

def tap(dev_x, dev_y):
    """Tap using idb ui tap — works reliably for all elements including toolbar items."""
    udid = get_booted_device()["udid"]
    result = subprocess.run(
        ["idb", "ui", "tap", "--udid", udid, str(int(dev_x)), str(int(dev_y))],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"idb tap failed: {result.stderr.strip()}")
    else:
        print(f"Tapped ({dev_x}, {dev_y}) via idb")

def long_press(dev_x, dev_y, duration=2.0):
    """Long press using idb ui tap --duration. Triggers SwiftUI .contextMenu."""
    udid = get_booted_device()["udid"]
    result = subprocess.run(
        ["idb", "ui", "tap", "--udid", udid, "--duration", str(duration), str(int(dev_x)), str(int(dev_y))],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"idb long press failed: {result.stderr.strip()}")
    else:
        print(f"Long pressed ({dev_x}, {dev_y}) for {duration}s via idb")

def swipe(start_dev_x, start_dev_y, end_dev_x, end_dev_y, steps=20, step_delay=0.015):
    """Swipe using CGEvent drag — reliable for scroll and swipe-back gestures."""
    import Quartz

    focus_sim()
    sx, sy = dev_to_mac(start_dev_x, start_dev_y)
    ex, ey = dev_to_mac(end_dev_x, end_dev_y)

    event = Quartz.CGEventCreateMouseEvent(None, Quartz.kCGEventLeftMouseDown, (sx, sy), Quartz.kCGMouseButtonLeft)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)
    time.sleep(0.05)

    for i in range(1, steps + 1):
        x = sx + (ex - sx) * i / steps
        y = sy + (ey - sy) * i / steps
        event = Quartz.CGEventCreateMouseEvent(None, Quartz.kCGEventLeftMouseDragged, (x, y), Quartz.kCGMouseButtonLeft)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)
        time.sleep(step_delay)

    event = Quartz.CGEventCreateMouseEvent(None, Quartz.kCGEventLeftMouseUp, (ex, ey), Quartz.kCGMouseButtonLeft)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)

def swipe_back():
    dw = device_w()
    swipe(5, device_h() // 2, dw * 0.62, device_h() // 2)
    print("Swiped back")

def swipe_up():
    cx = device_w() // 2
    swipe(cx, device_h() * 0.69, cx, device_h() * 0.34)
    print("Swiped up (scroll down)")

def swipe_down():
    cx = device_w() // 2
    swipe(cx, device_h() * 0.34, cx, device_h() * 0.69)
    print("Swiped down (scroll up)")

def type_text(text):
    focus_sim()
    # Escape special AppleScript characters
    escaped = text.replace("\\", "\\\\").replace('"', '\\"')
    subprocess.run(["osascript", "-e", f'tell application "System Events" to keystroke "{escaped}"'], capture_output=True)
    print(f"Typed: {text}")

def screenshot(out_path="/tmp/sim_screenshot.png", grid_spacing=25):
    """Take a screenshot with a coordinate grid overlay in device points.
    Grid every 25pt, labels on 50pt lines, bold on 100pt lines."""
    from PIL import Image, ImageDraw, ImageFont

    raw = "/tmp/sim_raw.png"
    subprocess.run(["xcrun", "simctl", "io", "booted", "screenshot", raw],
                   capture_output=True, text=True)

    dw, dh = device_w(), device_h()
    img = Image.open(raw).convert("RGBA")
    raw_w, raw_h = img.size

    overlay = Image.new("RGBA", (raw_w, raw_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    sx = raw_w / dw
    sy = raw_h / dh

    font_size = max(int(sx * 7), 16)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/SFNSMono.ttf", font_size)
    except (OSError, IOError):
        try:
            font = ImageFont.truetype("/System/Library/Fonts/Menlo.ttc", font_size)
        except (OSError, IOError):
            font = ImageFont.load_default()

    minor_color = (255, 0, 0, 50)
    mid_color   = (255, 0, 0, 90)
    major_color = (255, 0, 0, 140)
    label_color = (255, 0, 0, 210)

    for dev_x in range(0, dw + 1, grid_spacing):
        px = int(dev_x * sx)
        if dev_x % 100 == 0:
            draw.line([(px, 0), (px, raw_h)], fill=major_color, width=3)
        elif dev_x % 50 == 0:
            draw.line([(px, 0), (px, raw_h)], fill=mid_color, width=2)
        else:
            draw.line([(px, 0), (px, raw_h)], fill=minor_color, width=1)
        if dev_x % 50 == 0:
            draw.text((px + 3, 3), str(dev_x), fill=label_color, font=font)

    for dev_y in range(0, dh + 1, grid_spacing):
        py = int(dev_y * sy)
        if dev_y % 100 == 0:
            draw.line([(0, py), (raw_w, py)], fill=major_color, width=3)
        elif dev_y % 50 == 0:
            draw.line([(0, py), (raw_w, py)], fill=mid_color, width=2)
        else:
            draw.line([(0, py), (raw_w, py)], fill=minor_color, width=1)
        if dev_y % 50 == 0:
            draw.text((3, py + 3), str(dev_y), fill=label_color, font=font)

    img = Image.alpha_composite(img, overlay).convert("RGB")

    max_h = 1800
    if raw_h > max_h:
        new_w = int(raw_w * max_h / raw_h)
        img = img.resize((new_w, max_h), Image.LANCZOS)

    img.save(out_path)
    print(f"Grid screenshot saved to {out_path} ({dw}x{dh}pt, grid every {grid_spacing}pt)")

def info():
    dev = get_booted_device()
    print(f"Device: {dev['name']}")
    print(f"UDID:   {dev['udid']}")
    print(f"Points: {dev['w']}x{dev['h']}")

# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "tap" and len(sys.argv) >= 4:
        tap(float(sys.argv[2]), float(sys.argv[3]))
    elif cmd == "long_press" and len(sys.argv) >= 4:
        dur = float(sys.argv[4]) if len(sys.argv) >= 5 else 2.0
        long_press(float(sys.argv[2]), float(sys.argv[3]), dur)
    elif cmd == "swipe_back":
        swipe_back()
    elif cmd == "swipe_up":
        swipe_up()
    elif cmd == "swipe_down":
        swipe_down()
    elif cmd == "screenshot":
        path = sys.argv[2] if len(sys.argv) >= 3 else "/tmp/sim_screenshot.png"
        screenshot(path)
    elif cmd == "info":
        info()
    elif cmd == "type" and len(sys.argv) >= 3:
        type_text(" ".join(sys.argv[2:]))
    else:
        print(__doc__)
        sys.exit(1)

---
name: iphone-sim
description: "Interact with the iPhone Simulator — navigate via accessibility tree, tap UI elements, type text, swipe, and control device settings. Use when asked to test, interact with, or verify anything in the iOS Simulator."
argument-hint: "[screenshot | tap <description> | type <text> | swipe <direction> | home | launch <bundle-id> | terminate <bundle-id> | dark | light | status-bar]"
user-invokable: true
---

# iPhone Simulator Control

You are controlling an iOS Simulator running on macOS. Use the **sim_helper.py** script, `xcrun simctl`, `idb`, and `osascript` to interact with it.

**The user's request:** $ARGUMENTS

## Core Workflow

1. **Focus** the simulator: `osascript -e 'tell application "Simulator" to activate'`
2. **Describe** the screen: `idb ui describe-all` to get element types, labels, and frames
3. **Act** — use `sim_helper.py` for tapping, typing, swiping (see below)
4. **Verify** — take a grid screenshot or describe again for visual confirmation
5. **Report** what happened

## sim_helper.py — Primary Interaction Tool

**Path:** `/Users/adamsulik/Documents/git/simulator-control/.claude/skills/iphone-sim/sim_helper.py`

This script uses `idb ui tap` for taps, AppleScript `keystroke` for typing, CGEvent mouse drag for swiping, and CGEvent mouseDown/hold for long presses.

**All coordinates are in device POINTS, NOT pixels.**

**Auto-detection:** The script auto-detects the booted simulator device and its point dimensions. No manual configuration needed. Run `python3 $SH info` to see detected device.

```bash
SH=/Users/adamsulik/Documents/git/simulator-control/.claude/skills/iphone-sim/sim_helper.py

python3 $SH tap 196 445            # Tap at device point (x, y)
python3 $SH long_press 200 490     # Long press (for context menus, 2s default)
python3 $SH long_press 200 490 3.0 # Long press with custom duration
python3 $SH swipe_back             # iOS swipe-back gesture (left edge → right)
python3 $SH swipe_up               # Scroll down (swipe content up)
python3 $SH swipe_down             # Scroll up (swipe content down)
python3 $SH type "hello world"     # Type into focused field
python3 $SH screenshot             # Screenshot with coordinate grid overlay
python3 $SH screenshot /tmp/s.png  # Screenshot to custom path
python3 $SH info                   # Show booted device name and dimensions
```

**Dependencies:** Requires `pyobjc-framework-Quartz`, `Pillow`, and `idb`. Install with:
```bash
pip3 install --break-system-packages pyobjc-framework-Quartz Pillow
brew install idb-companion && pip3 install --break-system-packages fb-idb
```

## What Works vs What Doesn't

| Method | Tapping | Long Press | Typing | Swiping |
|--------|---------|------------|--------|---------|
| **sim_helper.py** | **YES** (idb) | **YES** (idb) | **YES** (AppleScript) | **YES** (CGEvent) |
| idb ui tap | **YES** | **YES** (--duration) | NO | NO |
| cliclick | NO (unreliable) | NO | Partial | NO |

- **`idb ui tap`** works reliably for all elements including toolbar items. It's the primary tap method.
- **Long press** uses `idb ui tap --duration` — reliable, doesn't require Simulator to be frontmost.
- **Typing** uses AppleScript `keystroke` — requires Hardware Keyboard connected.
- **Swiping** uses CGEvent mouse drag — reliable for scroll and swipe-back gestures.

## Screenshots with Coordinate Grid

The `screenshot` command captures the screen and overlays a coordinate grid in device points:

```bash
SH=/Users/adamsulik/Documents/git/simulator-control/.claude/skills/iphone-sim/sim_helper.py

# Take a grid screenshot (default: /tmp/sim_screenshot.png)
python3 $SH screenshot

# Take to custom path
python3 $SH screenshot /tmp/my_screenshot.png
```

The grid has three visual tiers:
- **Every 25pt** — faint red lines
- **Every 50pt** — medium red lines with coordinate labels
- **Every 100pt** — bold red lines with coordinate labels

The screenshot is auto-resized to max 1800px height for readability.

Use the Read tool to view the PNG. The grid makes it easy to estimate tap coordinates for elements that don't appear in `idb ui describe-all`.

**For screenshots without the grid:**
```bash
xcrun simctl io booted screenshot /tmp/sim_screenshot.png && sips -Z 1800 /tmp/sim_screenshot.png --out /tmp/sim_screenshot.png
```

## Finding UI Elements

Use `idb ui describe-all` to get element frames in device points:

```bash
# Get all elements with labels
idb ui describe-all 2>&1 | python3 -c "
import json, sys
for el in json.load(sys.stdin):
    label = el.get('AXLabel', '') or ''
    t = el.get('type', '')
    if label:
        f = el['frame']
        cx = f['x'] + f['width']/2
        cy = f['y'] + f['height']/2
        print(f\"{t}: '{label}' center=({cx:.0f}, {cy:.0f}) frame={f}\")
"

# Find specific element
idb ui describe-all 2>&1 | python3 -c "
import json, sys
for el in json.load(sys.stdin):
    label = el.get('AXLabel', '') or ''
    if 'Login' in label:
        f = el['frame']
        print(f\"Found: center=({f['x']+f['width']/2:.0f}, {f['y']+f['height']/2:.0f})\")
"
```

Then tap the center coordinates with `sim_helper.py tap <cx> <cy>`.

### CRITICAL: `describe-all` vs `describe-point`

**`describe-all` has a known bug ([GitHub #767](https://github.com/facebook/idb/issues/767)): it does NOT return children of Group elements.** This means:
- **Tab Bar tabs** — invisible (Tab Bar is a Group)
- **Toolbar buttons** — invisible (toolbar is a Group)
- **Segmented picker segments** — invisible (picker is a TabGroup)

**`describe-point X Y` DOES find these elements.** When `describe-all` can't find something, probe specific coordinates:

```bash
# Probe a specific point — finds elements that describe-all misses
idb ui describe-point X Y 2>&1 | python3 -c "
import json, sys
el = json.load(sys.stdin)
print(f\"type={el['type']} label='{el.get('AXLabel','')}' role={el.get('role_description','')}\")
f = el['frame']
print(f\"center=({f['x']+f['width']/2:.0f}, {f['y']+f['height']/2:.0f})\")
"
```

**Strategy for finding elements:**
1. **First try `describe-all`** — search by `AXLabel` for regular buttons, text, links
2. **If not found, use `describe-point`** — probe the expected location (estimate from grid screenshot or nearby elements)
3. **Use grid screenshot** — take a screenshot with coordinate overlay to visually locate elements and read coordinates directly
4. **Last resort** — tap by estimated coordinates without verification

### Important: `.accessibilityIdentifier()` does NOT appear in idb

SwiftUI's `.accessibilityIdentifier()` is only used by XCUITest. It does **NOT** map to any field in idb's JSON output. The `AXUniqueId` field in idb maps to SF Symbol names on Images, not to programmatic identifiers.

**What DOES help in idb:**
- `.accessibilityLabel("Save")` → appears as `AXLabel` — this is how you find elements
- `Image(systemName: "heart")` → `AXUniqueId: "heart"` — only on SF Symbol Images
- `AXValue` — shows toggle state (0/1), text field content, etc.

**For simulator testing, `.accessibilityLabel()` is more useful than `.accessibilityIdentifier()`.**

## Workflow Example

```bash
SH=/Users/adamsulik/Documents/git/simulator-control/.claude/skills/iphone-sim/sim_helper.py

# 1. See what's on screen
idb ui describe-all 2>&1 | python3 -c "
import json, sys
for el in json.load(sys.stdin):
    label = el.get('AXLabel', '') or ''
    if label and el.get('type') == 'Button':
        f = el['frame']
        print(f\"Button: '{label}' center=({f['x']+f['width']/2:.0f}, {f['y']+f['height']/2:.0f})\")
"
# Output: Button: 'Log In' center=(196, 760)

# 2. Tap it
python3 $SH tap 196 760

# 3. Verify with grid screenshot
python3 $SH screenshot
# Then use Read tool to view /tmp/sim_screenshot.png
```

## Typing into Text Fields

```bash
SH=/Users/adamsulik/Documents/git/simulator-control/.claude/skills/iphone-sim/sim_helper.py

# 1. Find the text field
idb ui describe-all 2>&1 | python3 -c "
import json, sys
for el in json.load(sys.stdin):
    if el.get('type') == 'TextField':
        f = el['frame']
        print(f\"TextField: val='{el.get('AXValue','')}' center=({f['x']+f['width']/2:.0f}, {f['y']+f['height']/2:.0f})\")
"

# 2. Tap to focus
python3 $SH tap 196 445

# 3. Type
python3 $SH type "admin@schoolsquad.app"
```

### Multi-Field Entry — IMPORTANT

When typing into multiple fields sequentially, **always dismiss the keyboard between fields**. If the keyboard is open, tapping the next field often fails silently — text goes into the still-focused field.

```bash
# Type into first field
python3 $SH tap 196 445
python3 $SH type "first value"

# DISMISS KEYBOARD before moving to next field — use one of:
osascript -e 'tell application "System Events" to key code 48'   # Tab to next field
osascript -e 'tell application "System Events" to key code 36'   # Return key
python3 $SH tap 196 600                                          # Tap empty area
sleep 0.5

# Now tap and type into second field
python3 $SH tap 196 545
python3 $SH type "second value"
```

## App Lifecycle

```bash
xcrun simctl launch booted <bundle-id>
xcrun simctl launch --console booted <bundle-id>    # with stdout
xcrun simctl terminate booted <bundle-id>
xcrun simctl uninstall booted <bundle-id>
xcrun simctl install booted /path/to/App.app
xcrun simctl openurl booted "myapp://deep-link"
```

## Device Controls

```bash
# Appearance
xcrun simctl ui booted appearance dark
xcrun simctl ui booted appearance light

# Status bar (clean for screenshots)
xcrun simctl status_bar booted override --time "9:41" --batteryState charged --batteryLevel 100 --wifiBars 3 --cellularBars 4
xcrun simctl status_bar booted clear

# Location
xcrun simctl location booted set 42.3601,-71.0589

# Permissions (grant without prompts)
xcrun simctl privacy booted grant photos <bundle-id>
xcrun simctl privacy booted grant camera <bundle-id>
xcrun simctl privacy booted grant location <bundle-id>

# Pasteboard
echo -n "text" | xcrun simctl pbcopy booted
xcrun simctl pbpaste booted

# Add media
xcrun simctl addmedia booted /path/to/photo.jpg
```

## Menu Automation (AppleScript)

```bash
# Home button (most reliable way)
osascript -e 'tell application "System Events" to tell process "Simulator" to click menu item "Home" of menu "Device" of menu bar 1'

# Shake gesture
osascript -e 'tell application "System Events" to tell process "Simulator" to click menu item "Shake" of menu "Device" of menu bar 1'

# Rotate
osascript -e 'tell application "System Events" to tell process "Simulator" to click menu item "Rotate Left" of menu "Device" of menu bar 1'

# Toggle hardware keyboard
osascript -e 'tell application "System Events" to tell process "Simulator" to click menu item "Connect Hardware Keyboard" of menu "Keyboard" of menu item "Keyboard" of menu "I/O" of menu bar 1'

# Toggle software keyboard
osascript -e 'tell application "System Events" to tell process "Simulator" to click menu item "Toggle Software Keyboard" of menu "Keyboard" of menu item "Keyboard" of menu "I/O" of menu bar 1'
```

## SwiftUI Accessibility Tree Gaps

Some SwiftUI elements do NOT appear in `idb ui describe-all`:

| Element | In Tree? | Workaround |
|---------|----------|------------|
| Button, Text, NavigationLink | YES | Use accessibility tree |
| **`.toolbar { ToolbarItem }` buttons** | **NO** | Use `describe-point` at expected position, or grid screenshot |
| **TabView tab items** | **NO** (single Group) | Tap by calculated position or grid screenshot |
| Segmented Picker (`.pickerStyle(.segmented)`) | Partial (TabGroup only, no segments) | Tap left/right half of TabGroup frame |

**When an element is missing from the tree:**
1. **Take a grid screenshot** (`python3 $SH screenshot`) — read coordinates directly from the overlay
2. **Use `describe-point`** — probe the expected location to confirm what's there
3. **Add `.accessibilityLabel()` to the element in SwiftUI code**, rebuild, and relaunch for permanent fix
4. For **toolbar buttons**: nav bar is typically at `y:56, height:44` (center `y~78`). `.confirmationAction` is far right.
5. For **tab bar items**: divide the tab bar width evenly by number of tabs.

### Best Practice: Always Add Accessibility Identifiers

When writing new SwiftUI views, **always add `.accessibilityIdentifier()` to elements that won't be in the tree by default**. This includes:

```swift
// Toolbar items — NOT in tree by default
.toolbar {
    ToolbarItem(placement: .confirmationAction) {
        Button("Save") { ... }
            .accessibilityIdentifier("save-button")
    }
}

// Tab items — NOT individually in tree by default
TabView {
    HomeView()
        .tabItem { Label("Home", systemImage: "house") }
        .accessibilityIdentifier("home-tab")
    ProfileView()
        .tabItem { Label("Profile", systemImage: "person") }
        .accessibilityIdentifier("profile-tab")
}

// Segmented pickers — segments not individually exposed
Picker("Method", selection: $method) { ... }
    .pickerStyle(.segmented)
    .accessibilityIdentifier("payment-method-picker")
```

This makes simulator testing reliable AND improves VoiceOver accessibility.

**Tip:** Run `/iphone-sim-setup` to automatically scan the codebase and add missing identifiers before testing.

## Common Pitfalls

- **Do NOT use `cliclick c:`** for tapping — unreliable. Use `sim_helper.py tap` instead.
- **Coordinates are device POINTS**, not pixels. Use `idb ui describe-all` for frames.
- **Typing into wrong field** — keyboard covers other fields. Always dismiss keyboard before tapping next field (Tab key, Return, or tap empty area).
- **Typing fails silently**: Hardware Keyboard must be connected (I/O > Keyboard). The text field IS focused even without a visible software keyboard.
- **Lock screen stuck on black**: Use Device > Home menu to wake. Do NOT try to swipe-unlock.
- **`openurl` opens Safari**: Expected for http URLs. Use `xcrun simctl launch` to switch back.
- **Multiple simulators**: Use UDID instead of "booted" if more than one sim is running.
- **Long press fails**: Make sure idb companion is connected (`idb connect <UDID>`). Long press uses `idb ui tap --duration` which doesn't require Simulator to be frontmost.
- **idb companion not connected**: If `idb ui describe-all` fails, reconnect: `idb connect <UDID>`. If that fails, restart the companion with `idb_companion --udid <UDID> --grpc-domain-sock /tmp/idb/<UDID>_companion.sock`.

# iPhone Simulator Control for Claude Code

A [Claude Code](https://docs.anthropic.com/en/docs/claude-code) toolkit for full iOS Simulator control — skills, a helper script, and a QA agent that can test your app autonomously.

## What's Included

| Path | What it does |
|------|-------------|
| `.claude/skills/iphone-sim/SKILL.md` | Skill for interacting with the simulator (tap, type, swipe, screenshot, etc.) |
| `.claude/skills/iphone-sim/sim_helper.py` | Helper script — handles tapping (idb), long press, swiping (CGEvent), typing (AppleScript), and grid screenshots (Pillow) |
| `.claude/skills/iphone-sim-setup/SKILL.md` | Skill for scanning SwiftUI views and adding accessibility modifiers so elements are findable in the simulator |
| `.claude/agents/ios-qa-engineer.md` | Autonomous QA agent that tests iOS app features in the simulator, reports bugs with screenshots |

## Installation

### 1. Copy into your Claude Code config

```bash
# Skills (global — available in all projects)
cp -r .claude/skills/iphone-sim ~/.claude/skills/
cp -r .claude/skills/iphone-sim-setup ~/.claude/skills/

# Agent (global)
mkdir -p ~/.claude/agents
cp .claude/agents/ios-qa-engineer.md ~/.claude/agents/

# Or keep project-level — clone this repo and the .claude/ dir is picked up automatically
```

### 2. Install dependencies

```bash
# Required — simulator interaction
pip3 install --break-system-packages pyobjc-framework-Quartz Pillow
brew install idb-companion && pip3 install --break-system-packages fb-idb

# Verify
xcrun simctl list devices booted    # Need Xcode + a booted simulator
idb describe --udid booted          # idb companion connected
```

### 3. One-time simulator setup

```bash
# Show touch dots in the simulator (persists across launches, restart Simulator after)
defaults write com.apple.iphonesimulator ShowSingleTouches 1

# Connect idb to the booted simulator
UDID=$(xcrun simctl list devices booted -j | python3 -c "import json,sys; [print(d['udid']) for r in json.load(sys.stdin)['devices'].values() for d in r if d['state']=='Booted']" 2>/dev/null | head -1)
idb connect "$UDID"
```

## Usage

### Skills

Once installed, use the skills via slash commands or let Claude invoke them automatically:

```
/iphone-sim screenshot              Take a grid screenshot with coordinate overlay
/iphone-sim tap the Login button    Find and tap an element
/iphone-sim type "hello@test.com"   Type into the focused field
/iphone-sim swipe up                Scroll down
/iphone-sim launch com.myapp.id     Launch an app

/iphone-sim-setup                   Scan SwiftUI views and add missing accessibility modifiers
```

Or ask naturally:

```
> Take a screenshot of the simulator
> Tap on Settings and enable Dark Mode
> Fill in the login form and submit it
```

### QA Agent

The `ios-qa-engineer` agent can autonomously test features in the simulator. It takes screenshots at every step, tests edge cases, and reports bugs with severity levels.

Claude will launch the agent automatically when you:
- Ask it to test a feature
- Finish implementing something and want verification
- Fix a bug and want regression testing

Or launch it explicitly:

```
> Can you test the login flow?
> I just finished the profile screen, test it
> Verify the chat moderation features work
```

## How It Works

### Coordinate Grid Screenshots

Most simulator tools give Claude a raw screenshot and hope it can guess where to tap. That works for obvious buttons, but falls apart for toolbar items, tab bars, or anything the accessibility tree can't see.

Our approach: **overlay a coordinate grid directly on the screenshot.** Claude reads the exact point coordinates off the image — no guessing, no pixel-to-point math, no "tap roughly in the middle of the screen."

The grid has three tiers of visual density:
- Faint lines every **25pt** — fine-grained positioning
- Medium lines with labels every **50pt** — quick coordinate reading
- Bold lines with labels every **100pt** — major landmarks

The screenshot is auto-resized to fit within Claude's image limits (max 1800px height) while preserving the coordinate mapping. This means Claude can locate and tap *any* visible element — even ones completely invisible to the accessibility tree.

### Interaction Methods

| Action | Method | Tool |
|--------|--------|------|
| **Tap** | `idb ui tap` | Accessibility API — works for all elements including toolbar items |
| **Long press** | `idb ui tap --duration` | Triggers SwiftUI `.contextMenu` reliably |
| **Type** | AppleScript `keystroke` | Requires Hardware Keyboard connected in Simulator |
| **Swipe** | CGEvent mouse drag | Reliable for scroll and swipe-back gestures |
| **Screenshot** | `xcrun simctl io` + Pillow grid overlay | 25pt coordinate grid, auto-resized |

### Finding UI Elements

Claude uses a three-tier strategy to locate elements:

1. **`idb ui describe-all`** — returns all elements with `AXLabel` and frames in device points. Fast, structured, preferred when it works.
2. **`idb ui describe-point X Y`** — probes a specific coordinate. Finds toolbar buttons, tab bar items, and segmented picker segments that `describe-all` misses due to the Group children bug ([idb #767](https://github.com/facebook/idb/issues/767)).
3. **Grid screenshot** — the visual fallback. Claude reads coordinates directly from the overlay and taps with precision. This is what makes the toolkit reliable even when the accessibility tree has gaps.

### The `describe-all` Group Children Bug

`idb ui describe-all` does NOT return children of Group elements. This means toolbar buttons, tab bar items, and segmented picker segments are invisible to the most common discovery method. Other tools work around this by having the AI guess coordinates from raw screenshots — which is fragile and error-prone.

We solve this two ways:
1. **Grid screenshots** give Claude exact coordinates for anything visible on screen, regardless of accessibility tree coverage
2. **`iphone-sim-setup` skill** scans SwiftUI code and adds `.accessibilityLabel()` / `.accessibilityIdentifier()` modifiers, making elements permanently discoverable

## Capabilities

- Grid screenshots with coordinate overlay (25pt resolution)
- Tap, long press, swipe (back, up, down)
- Text input with keyboard management
- App lifecycle (launch, terminate, install, uninstall, deep links)
- Device controls (dark/light mode, status bar, location, permissions)
- Menu automation (Home, Shake, Rotate, keyboard toggles)
- SwiftUI accessibility audit and modifier injection
- Autonomous QA testing with bug reports

## License

MIT License — see [LICENSE](LICENSE).

Copyright (c) 2026 Warped Technologies LLC. Created by Adam Sulik.

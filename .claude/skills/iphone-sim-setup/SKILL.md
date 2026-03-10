---
name: iphone-sim-setup
description: "Scan SwiftUI views for elements invisible or indistinguishable in the idb accessibility tree and add accessibility modifiers. Run before simulator testing or after adding new views."
user-invokable: true
---

# Accessibility Setup for iOS Simulator Testing

This skill does two things:
1. **One-time environment setup** — installs tools and enables simulator settings needed for testing
2. **Codebase scan** — finds SwiftUI elements that are invisible/indistinguishable in idb and adds accessibility modifiers

---

## Phase 0: Prerequisites (One-Time Setup)

Run these checks first. Skip any that are already done.

### 1. Install dependencies

```bash
# Check if already installed
python3 -c "import Quartz" 2>/dev/null || pip3 install --break-system-packages pyobjc-framework-Quartz
python3 -c "from PIL import Image" 2>/dev/null || pip3 install --break-system-packages Pillow
which idb >/dev/null 2>&1 || (brew install idb-companion && pip3 install --break-system-packages fb-idb)
```

### 2. Enable touch visualization in Simulator

Shows a dot where touches land — essential for debugging tap accuracy:

```bash
defaults write com.apple.iphonesimulator ShowSingleTouches 1
```

Restart Simulator after setting this. The setting persists across launches.

### 3. Connect idb companion

idb needs a companion process connected to the booted simulator:

```bash
# Check if idb can talk to the booted sim
idb describe --udid booted 2>/dev/null

# If that fails, connect manually:
UDID=$(xcrun simctl list devices booted -j | python3 -c "import json,sys; [print(d['udid']) for r in json.load(sys.stdin)['devices'].values() for d in r if d['state']=='Booted']" 2>/dev/null | head -1)
idb connect "$UDID"
```

If `idb connect` fails with a socket error, restart the companion:
```bash
# Kill old companion
pkill -f idb_companion
# Remove stale socket
rm -f /tmp/idb/${UDID}_companion.sock
# Restart with Unix domain socket
idb_companion --udid "$UDID" --grpc-domain-sock "/tmp/idb/${UDID}_companion.sock" &
sleep 2
idb connect "$UDID"
```

### 4. Verify sim_helper.py

```bash
SH=/Users/adamsulik/Documents/git/simulator-control/.claude/skills/iphone-sim/sim_helper.py
python3 $SH info
# Should print: Device: iPhone 16 Pro, UDID: ..., Points: 402x874
```

---

## Phase 1: Codebase Scan

`idb ui describe-all` is the primary way to find UI elements for simulator testing. But many SwiftUI elements are either **invisible** (not in the tree at all) or **indistinguishable** (present but identical to other elements). This phase scans the codebase and fixes both problems.

## CRITICAL: How idb Maps to SwiftUI Accessibility Modifiers

Understanding this mapping is essential — using the wrong modifier wastes effort:

| SwiftUI Modifier | idb Field | Searchable in `describe-all`? | Purpose |
|-----------------|-----------|-------------------------------|---------|
| `.accessibilityLabel("Save")` | `AXLabel` | **YES** — this is how you find elements | VoiceOver + idb testing |
| `.accessibilityIdentifier("save-button")` | **NONE** — invisible to idb | **NO** | XCUITest only |
| `Button("Save")` (text label) | `AXLabel` (automatic) | **YES** | Already works |
| `Image(systemName: "heart")` | `AXUniqueId: "heart"` | YES (Images only) | SF Symbol lookup |

**Key takeaway:** `.accessibilityLabel()` is what makes elements findable in idb. `.accessibilityIdentifier()` is useful for XCUITest but completely invisible to idb.

### The `describe-all` Group Children Bug (idb #767)

`idb ui describe-all` does NOT return children of Group elements. This means:
- **Tab Bar tabs** — invisible (Tab Bar is a Group)
- **Toolbar buttons** — invisible (Toolbar is a Group)
- **Segmented picker segments** — invisible (Picker is a TabGroup)

**No modifier fixes this.** These elements are findable via `idb ui describe-point X Y` (which DOES return Group children), but NOT via `describe-all`.

Adding `.accessibilityIdentifier()` to these elements is still valuable for XCUITest automation, but it won't help idb-based simulator testing.

---

## What to Scan For

### Tier 1: INVISIBLE — Not in `describe-all` (Group children bug)

These elements do NOT appear in `idb ui describe-all` due to the Group children bug. They CAN be found via `describe-point` at their coordinates. Elements with text labels (like `Button("Save")`) already have `AXLabel` when probed with `describe-point`.

**Why still add `.accessibilityIdentifier()`:** XCUITest automation, future-proofing, code self-documentation.

| Pattern | Grep Pattern | Fix |
|---------|-------------|-----|
| Toolbar buttons | `ToolbarItem` | `.accessibilityIdentifier()` on the Button inside |
| Tab items | `.tabItem` | `.accessibilityIdentifier()` after `.tabItem { }` |
| Segmented pickers | `.pickerStyle(.segmented)` | `.accessibilityIdentifier()` after the picker style |

### Tier 2: INDISTINGUISHABLE — In tree but can't tell them apart

These appear in `describe-all` as generic types with no distinguishing label. **`.accessibilityLabel()` is the primary fix** — it maps to `AXLabel` in idb, making these elements searchable.

| Pattern | Problem in idb | Grep Pattern | Fix |
|---------|---------------|-------------|-----|
| Icon-only buttons | Shows as `Button` with NO `AXLabel` | See detection rules below | `.accessibilityLabel()` (idb) AND `.accessibilityIdentifier()` (XCUITest) |
| Multiple TextFields | All show as `TextField` — only position differs | `TextField(` | `.accessibilityIdentifier()` on each (placeholder already serves as label) |
| DisclosureGroup | May not be reliably findable | `DisclosureGroup` | `.accessibilityIdentifier()` |

### Tier 3: SOMETIMES MISSING — Depends on presentation context

| Pattern | Grep Pattern | Fix |
|---------|-------------|-----|
| Sheets | `.sheet(` | `.accessibilityIdentifier()` on root view inside sheet |
| Full screen covers | `.fullScreenCover(` | Same |
| Popovers | `.popover(` | Same |

### DO NOT TOUCH — Already works fine in idb

| Pattern | Why it's fine |
|---------|--------------|
| `Button("Label Text")` | Text automatically becomes `AXLabel` — visible in idb |
| `NavigationLink` | Visible as Button with `AXLabel` from its text |
| `Text`, `Image` (non-interactive) | Visible, rarely need interaction |
| `.alert(` / `.confirmationDialog(` | System-presented — modifiers don't propagate to system UI |

---

## Workflow

### Step 1: Find all Swift view files

```
Glob **/*.swift (excluding tests, packages, build directories)
```

### Step 2: Search for each pattern

Run Grep for each pattern in the tables above. For each file with matches, Read the file and check each match.

**Skip check:** Look within 5 lines after each match for `.accessibilityIdentifier(` or `.accessibilityLabel(`. If found, skip it.

### Step 3: Add modifiers

#### Toolbar Buttons
Derive from button label, kebab-case, suffixed with `-button`:
```swift
// Before:
ToolbarItem(placement: .confirmationAction) {
    Button("Save") { ... }
}
// After:
ToolbarItem(placement: .confirmationAction) {
    Button("Save") { ... }
        .accessibilityIdentifier("save-button")
}
```

**Note:** The button text "Save" already becomes `AXLabel` automatically — no `.accessibilityLabel()` needed. The `.accessibilityIdentifier()` is for XCUITest only (invisible to idb). These buttons are findable via `idb ui describe-point` at their coordinates.

#### Tab Items
Derive from Label text, suffixed with `-tab`:
```swift
// Before:
ProfileView()
    .tabItem { Label("Profile", systemImage: "person") }
// After:
ProfileView()
    .tabItem { Label("Profile", systemImage: "person") }
    .accessibilityIdentifier("profile-tab")
```

**Note:** Same as toolbar buttons — the Label text is already `AXLabel` via `describe-point`. The identifier helps XCUITest.

#### Segmented Pickers
Derive from Picker label or binding variable, suffixed with `-picker`:
```swift
// Before:
Picker("Payment method", selection: $viewModel.paymentMethod) { ... }
    .pickerStyle(.segmented)
// After:
Picker("Payment method", selection: $viewModel.paymentMethod) { ... }
    .pickerStyle(.segmented)
    .accessibilityIdentifier("payment-method-picker")
```

#### Icon-Only Buttons (MOST IMPORTANT for idb)
Detect buttons whose label content is ONLY an `Image(systemName:)` with no accompanying Text, and no existing `.accessibilityLabel()`. These need BOTH modifiers — **`.accessibilityLabel()` is the critical one** because it makes the button findable by `AXLabel` in idb:

```swift
// Before:
Button {
    showPassword.toggle()
} label: {
    Image(systemName: showPassword ? "eye.slash" : "eye")
}
// After:
Button {
    showPassword.toggle()
} label: {
    Image(systemName: showPassword ? "eye.slash" : "eye")
}
.accessibilityLabel("Toggle password visibility")
.accessibilityIdentifier("toggle-password-button")
```

**How to detect icon-only buttons:**
1. Search for `Button` followed by `Image(systemName:` within its label/content closure
2. Check that there is NO `Text(` sibling inside the same closure
3. Check that there is NO `.accessibilityLabel(` already applied

**Naming for icon-only buttons** — derive from SF Symbol name and context:
- `"eye"` / `"eye.slash"` near password → label `"Toggle password visibility"`, id `"toggle-password-button"`
- `"plus"` in toolbar → label `"Create"`, id `"create-button"`
- `"heart"` / `"heart.fill"` → label `"Favorite"`, id `"favorite-button"`
- `"bell"` / `"bell.badge"` → label `"Notifications"`, id `"notifications-button"`
- `"xmark"` → label `"Close"`, id `"close-button"`
- `"trash"` → label `"Delete"`, id `"delete-button"`
- `"pencil"` / `"square.and.pencil"` → label `"Edit"`, id `"edit-button"`
- `"gearshape"` → label `"Settings"`, id `"settings-button"`
- For other symbols, derive a reasonable name from the symbol name and surrounding code context

#### Multiple TextFields
When a view has 2+ TextFields, add identifier to each. Derive from placeholder or binding:
```swift
// From placeholder:
TextField("Enter email", text: $email)
    .accessibilityIdentifier("enter-email-field")

// From binding when placeholder is empty/generic:
TextField("", text: $pledgeAmount)
    .accessibilityIdentifier("pledge-amount-field")

// SecureField too:
SecureField("Password", text: $password)
    .accessibilityIdentifier("password-field")
```

**Note:** TextField placeholder text already appears as the accessibility label in idb. The `.accessibilityIdentifier()` adds XCUITest support and makes the intent clearer in code.

**Naming:** Use placeholder text (kebab-cased) with `-field` suffix. If placeholder is empty or generic (like "Amount"), fall back to the binding variable name.

#### DisclosureGroup
```swift
// Before:
DisclosureGroup("Pledges (\(count))") { ... }
// After:
DisclosureGroup("Pledges (\(count))") { ... }
    .accessibilityIdentifier("pledges-disclosure")
```

#### Sheets / Full Screen Covers / Popovers
Add identifier to the root view inside:
```swift
// Before:
.sheet(isPresented: $showEdit) {
    EditProfileView()
}
// After:
.sheet(isPresented: $showEdit) {
    EditProfileView()
        .accessibilityIdentifier("edit-profile-sheet")
}
```

### Step 4: Detect ForEach with interactive elements (WARN ONLY)

Search for `ForEach` blocks that contain `Button`, `TextField`, `NavigationLink`, `Toggle`, or `Picker` inside their closure. These produce multiple identical elements in idb and need **dynamic** identifiers that the skill CANNOT auto-generate.

**Do NOT auto-fix these.** Instead, report them:
```
ForEach with interactive elements (needs manual dynamic identifiers):
  - VolunteerSheet.swift:57 — Button inside ForEach(roles)
    Suggestion: .accessibilityIdentifier("signup-role-\(role.id)")
  - TakeSurveyView.swift:126 — Button inside ForEach(1...5) (rating stars)
    Suggestion: .accessibilityIdentifier("rating-star-\(star)")
  - CreateEventView.swift:34 — TextField inside ForEach(roles)
    Suggestion: .accessibilityIdentifier("role-name-\(index)")
```

### Step 5: Check for duplicate identifiers

After adding all identifiers, Grep the entire project for all `.accessibilityIdentifier("` strings. Extract the identifier values and check for duplicates across different files.

Same identifier in the same file is OK (e.g., in if/else branches). Same identifier in different files is a **warning**:
```
Duplicate identifiers across files:
  - "save-button" found in SchoolSettingsView.swift AND CreateEventView.swift
    → Consider: "save-school-settings-button", "save-event-button"
```

### Step 6: Report summary

```
Added modifiers (N total):
  Tier 1 (invisible to describe-all — identifiers for XCUITest):
    - SchoolSettingsView.swift: "save-button" (ToolbarItem)
    - MainTabView.swift: "home-tab", "events-tab", ... (5 tabs)
  Tier 2 (indistinguishable — labels for idb, identifiers for XCUITest):
    - LoginView.swift: label "Toggle password visibility" + id "toggle-password-button" (icon-only Button)
    - LoginView.swift: "email-field", "password-field" (TextFields)
    - FundraiserDetailView.swift: "pledges-disclosure" (DisclosureGroup)
  Tier 3 (sometimes missing):
    - EventDetailView.swift: "volunteer-sheet" (sheet root)

Skipped (already has modifier): N elements
  - MainTabView.swift: "profile-tab"
  - SchoolSettingsView.swift: "save-button"

ForEach needing manual identifiers: N locations
  - VolunteerSheet.swift:57 — Button inside ForEach

Duplicate identifiers: N pairs
  - "save-button" in 2 files
```

---

## Naming Convention Reference

| Element Type | Suffix | Example |
|-------------|--------|---------|
| Toolbar/regular button | `-button` | `"save-button"` |
| Tab | `-tab` | `"profile-tab"` |
| Picker | `-picker` | `"payment-method-picker"` |
| TextField / SecureField | `-field` | `"email-field"` |
| DisclosureGroup | `-disclosure` | `"pledges-disclosure"` |
| Sheet / cover / popover | `-sheet` | `"edit-profile-sheet"` |

**All identifiers use kebab-case.** Never camelCase, never snake_case.

---

## Important Rules

1. **Only modify patterns listed in the tables above** — do not add modifiers to elements that already work in idb
2. **Always check for existing modifiers before adding** — never duplicate
3. **Match surrounding code indentation exactly**
4. **Icon-only buttons get TWO modifiers**: `.accessibilityLabel()` (for idb `AXLabel`) AND `.accessibilityIdentifier()` (for XCUITest)
5. **ForEach elements are WARN ONLY** — never add static identifiers to dynamically generated elements
6. **Identifiers must be unique across the project** — check for and warn about duplicates
7. **SecureField counts as TextField** — treat them identically
8. **`.accessibilityLabel()` → `AXLabel` in idb** — this is the modifier that matters for simulator testing
9. **`.accessibilityIdentifier()` is invisible to idb** — only useful for XCUITest automation

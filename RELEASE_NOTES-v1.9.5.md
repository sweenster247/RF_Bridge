# RF Bridge v1.9.5

RF Bridge v1.9.5 is a UI refinement release focused on making the application feel cleaner, more intentional, and easier to read during live use.

## Added / Changed

- Added the RF Bridge logo treatment to the top-left sidebar brand area
- Refined the left navigation rail with a more application-like layout
- Reworked Capture Overlays into a wider, cleaner panel with a centered empty state
- Condensed the connected-device panel and aligned it with the RF Summary column
- Cleaned up visual artifacts/blocked backgrounds around section labels
- Improved spacing and panel balance across the top row

## Retained

- Confirmed-working v1.9.4.10 tinySA connection timing behavior
- Graph axis/cursor stability fixes from v1.9.4.11
- Overlay toggle safety fixes
- Sidebar layout direction from v1.9.4.12
- Mic Plot markers
- Capture overlays
- Profiles and Help/About menu
- Unified release build script

## Build

```bash
./build_release.sh
```

Release artifacts:

```text
dist/releases/RF-Bridge-v1.9.5-macOS-arm64.dmg
dist/releases/RF-Bridge-v1.9.5-macOS-arm64.zip
```

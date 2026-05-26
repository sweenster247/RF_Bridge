# RF Bridge v1.9.3 — Build Pipeline and Icon Update

RF Bridge v1.9.3 is a packaging and polish update focused on release consistency and app branding.

## Added

### Refined App Icon
- Rebuilt the macOS app icon using the RF Bridge logo artwork on a dark icon background
- Updated icon source assets for future `.icns` generation
- Build scripts now regenerate the icon when the PNG source is newer than the existing `.icns`


### Consolidated Release Build Script

- Added `build_release.sh`
- Builds the macOS `.app`
- Creates the DMG installer
- Creates a zipped `.app` release artifact
- Outputs release files under `dist/releases/`

### Standardized Release Artifact Names

Release artifacts now follow this pattern:

```text
RF-Bridge-v{version}-macOS-arm64.dmg
RF-Bridge-v{version}-macOS-arm64.zip
```

For this release:

```text
RF-Bridge-v1.9.3-macOS-arm64.dmg
RF-Bridge-v1.9.3-macOS-arm64.zip
```

### Updated App Icon Source

- Added RF Bridge logo artwork to `assets/Logo.png`
- Updated `assets/rf-bridge-icon-1024.png` from the new logo artwork
- Existing icon generation script now uses the updated icon source for future `.icns` builds

## Changed

- Updated `build_app.sh` to read the app version from `rf_bridge/version.py`
- Updated `build_dmg.sh` to output versioned arm64 release artifacts
- Updated PyInstaller bundle metadata to v1.9.3
- Updated README with the preferred RF Bridge logo header and release build workflow

## Retained

- Mic Plot markers
- Saved capture loading
- Live RF visualization
- Freeze Trace
- Peak hold modes
- tinySA auto-detection
- Connect/disconnect controls
- WWB-compatible CSV export
- Light/Dark/System appearance modes
- DMG distribution support

## Notes

This release remains unsigned. macOS may require right-click → Open on first launch.

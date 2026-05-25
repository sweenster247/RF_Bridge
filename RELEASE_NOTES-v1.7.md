# RF Bridge v1.7 — Polish + Distribution

RF Bridge v1.7 focuses on polish and distribution now that the packaged macOS app workflow is working.

## Added

- Preferences window under `RF Bridge > Preferences…`
- Appearance preference: `System`, `Dark`, or `Light`
- Persistent default refresh interval
- Persistent default storage folder for future app sessions
- App icon source assets
- macOS `.icns` generation helper script
- PyInstaller spec updated to use the RF Bridge icon
- DMG build script using `create-dmg`
- Documentation for app bundle and DMG workflows

## Retained

- Packaged macOS `.app` workflow
- GUI gig/session prompt
- GUI storage location prompt
- tinySA auto-detection
- Manual connect/disconnect
- Live RF graph
- Peak hold modes
- Freeze Trace
- WWB-compatible CSV export
- `latest_scan.csv` updating
- Headless/source script workflow

## Notes

This release is still unsigned. macOS may require right-click → Open on first launch.

DMG creation requires:

```bash
brew install create-dmg
```

Then run:

```bash
./build_app.sh
./build_dmg.sh
```

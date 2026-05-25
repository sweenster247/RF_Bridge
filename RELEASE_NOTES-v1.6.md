# RF Bridge v1.6 — First macOS App Build

RF Bridge v1.6 is the first release focused on turning the project into a double-clickable macOS app.

This release keeps the stable v1.5.1 PySide6/pyqtgraph desktop UI and adds the packaged-app launch behavior needed for `RF Bridge.app` builds.

## Highlights

### First packaged app workflow
- Added PyInstaller app bundle configuration
- Added `build_app.sh` for one-command local app builds
- Added app-bundle launch mode for double-click use
- Added GUI gig/session name prompt when launched as an app

### Better launch options
- Added `--app` to test packaged behavior from Terminal
- Added `--gig` to bypass the interactive gig-name prompt
- Added `--output-dir` to choose a custom scan output location

### Packaging improvements
- Improved PyInstaller hidden imports for PySide6, pyqtgraph, and pyserial
- Added macOS bundle metadata
- Updated README build instructions
- Bumped internal package version to `1.6.0`

## Retained from v1.5.1
- Threaded scan worker
- tinySA connection panel
- Connect/disconnect/refresh ports controls
- Device status, version, and range display
- In-app log pane
- Freeze Trace mode
- Persistent settings
- WWB-compatible CSV export
- `latest_scan.csv` live updating
- Qt thread-safety crash fix

## Build

From the project root on macOS:

```bash
./build_app.sh
```

The app bundle should be created at:

```text
dist/RF Bridge.app
```

## Notes

This release produces an unsigned local macOS app bundle. Code signing, notarization, and DMG creation are future release targets.

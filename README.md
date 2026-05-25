# RF Bridge v1.6.2

RF Bridge connects a tinySA to a Wireless Workbench-friendly CSV workflow with a live desktop RF display.

v1.6.2 builds on the first packaged-app milestone. It keeps the stable v1.5.1 threaded PySide6/pyqtgraph UI and adds a proper macOS app launch path so RF Bridge can be built as `RF Bridge.app` with PyInstaller.

## What changed in v1.6

- Added packaged-app launch mode for macOS builds
- Double-clicked app bundles now launch the desktop UI by default
- Added GUI gig/session name prompt for app launches
- Added `--app` mode for testing the packaged-app flow from Terminal
- Added `--gig` argument for launching without an interactive prompt
- Added `--output-dir` override for custom scan locations
- Improved PyInstaller spec for PySide6, pyqtgraph, and pyserial bundling
- Updated build script for one-command app bundle creation
- Bumped internal package version to `1.6.0`

## Install dependencies for source use

```bash
python3 -m pip install -r requirements.txt
```

## Run from source

Start the desktop UI:

```bash
python3 rf-bridge.py --ui
```

Test the packaged-app flow from Terminal:

```bash
python3 rf-bridge.py --app
```

Launch without a gig-name prompt:

```bash
python3 rf-bridge.py --ui --gig "Blues Fest"
```

Manual port:

```bash
python3 rf-bridge.py --ui --port /dev/cu.usbmodem4001
```

List ports:

```bash
python3 rf-bridge.py --list-ports
```

Set initial refresh interval:

```bash
python3 rf-bridge.py --ui --refresh 1
```

Headless CSV capture still works:

```bash
python3 rf-bridge.py
```

## Build the macOS app bundle

From the project root on macOS:

```bash
./build_app.sh
```

The unsigned app bundle should be created at:

```text
dist/RF Bridge.app
```

First launch on macOS may require:

```text
Right-click RF Bridge.app > Open > Open
```

That is expected for an unsigned local build.

## Recommended clean build workflow

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
./build_app.sh
```

## Project layout

```text
rf_bridge/config.py    shared defaults
rf_bridge/utils.py     time, safe names, number parsing
rf_bridge/tinysa.py    serial discovery and tinySA command helpers
rf_bridge/export.py    WWB CSV export and latest_scan.csv handling
rf_bridge/scanner.py   scan validation and headless scan loop
rf_bridge/worker.py    threaded tinySA scan worker for the UI
rf_bridge/settings.py  persistent PySide6/QSettings helpers
rf_bridge/ui.py        PySide6 + pyqtgraph UI
rf_bridge/app.py       command-line and packaged-app startup
rf-bridge.py           compatibility launcher
rf-bridge.spec         PyInstaller app bundle spec
build_app.sh           macOS app build helper
```

## v1.5.1 stability retained

- Background threaded scan worker
- tinySA connection panel
- Port refresh, connect, and disconnect controls
- Device status, version, and sweep range display
- In-app event log pane
- Freeze Trace mode
- Persistent settings using `QSettings`
- WWB-compatible CSV export
- `latest_scan.csv` live updating
- Headless CSV capture mode
- Qt thread-safety fix from v1.5.1

## v1.6.2 App Launch Polish

When launched as a packaged macOS app, RF Bridge now prompts in this order:

```text
1. Gig/session name
2. Storage location
3. Main RF Bridge window
```

The gig/session name field starts empty. If left blank, RF Bridge uses `RF Bridge Scan` as the fallback session name.

The default storage location is:

```text
~/Documents/RF Bridge
```

Scan files are saved inside the selected storage root using:

```text
wwb_scans/<gig>
```

For example, accepting the default storage location with a gig named `Blues Fest` saves to:

```text
~/Documents/RF Bridge/wwb_scans/blues_fest
```

## Notes

v1.6.2 does not include Apple code signing or notarization. That can come later after the app bundle flow is stable.


## v1.6.1 App Launch Fix

If you are building the macOS `.app`, use v1.6.1 or newer. This patch defers tinySA auto-detection until after the main window is visible, which prevents the packaged app from appearing to disappear after the gig/session prompt.

Packaged app scans are saved by default to:

```text
~/Documents/RF Bridge/wwb_scans/<gig>
```

The script workflow is unchanged:

```bash
python3 rf-bridge.py --ui
```


## v1.6.2 App Prompt Update

Use v1.6.2 or newer if you want the packaged app to ask for both gig/session name and scan storage location at launch. The Terminal/script workflow remains unchanged.

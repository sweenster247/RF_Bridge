# RF Bridge v1.9.1
<p align="center">
  <img src="https://github.com/sweenster247/RF_Bridge/blob/main/assets/%20Logo.png" width="650" alt="RF Bridge Logo">
</p>

RF Bridge connects a tinySA to a Wireless Workbench-friendly CSV workflow with a live desktop RF display.

v1.9 adds Mic Plot markers so wireless/mic frequencies can be manually labeled on top of live, frozen, or loaded RF captures. v1.9.1 improves Mic Plot label placement/readability.

## Highlights

- PySide6 + pyqtgraph desktop UI
- tinySA auto-detection and manual port selection
- Connect / Disconnect / Refresh Ports controls
- Live RF graph with peak hold modes
- Freeze Trace mode for inspecting a scan without stopping capture
- WWB-compatible CSV export
- `latest_scan.csv` live updating
- Persistent settings using `QSettings`
- Preferences window for appearance, default refresh, and default storage folder
- Dark / Light / System appearance options
- App icon source assets and macOS `.icns` generation script
- PyInstaller `.app` build script
- DMG build script using `create-dmg`
- Open saved RF Bridge CSV captures from the File menu
- Loaded Capture mode with Return to Live workflow

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

## Loading saved captures

Open a previous RF Bridge CSV scan from:

```text
File > Open Capture…
```

Supported files use the same two-column RF Bridge / WWB-friendly format:

```text
frequency_mhz, dbm
```

When a capture is loaded, the graph enters **Loaded Capture** mode. Live scanning can continue in the background if a tinySA is connected, and new scans will still save to disk. Use:

```text
File > Return to Live
```

or the **Return to Live** button to resume the live trace.

## Preferences

Open:

```text
RF Bridge > Preferences…
```

Preferences currently supports:

- Appearance: `System`, `Dark`, or `Light`
- Default refresh interval
- Default storage folder for future app sessions

Storage changes apply to new app sessions. The current scan session keeps writing to the folder selected at launch.

## Packaged app launch flow

When launched as a packaged macOS app, RF Bridge prompts in this order:

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

## Build the DMG

Install `create-dmg`:

```bash
brew install create-dmg
```

Build the app, then build the DMG:

```bash
./build_app.sh
./build_dmg.sh
```

The DMG should be created at:

```text
dist/RF-Bridge-v1.9-macOS.dmg
```

## App icon

v1.9 includes:

```text
assets/rf-bridge-icon-1024.png
assets/rf-bridge-icon.svg
scripts/create_icon.sh
```

`build_app.sh` automatically creates:

```text
assets/rf-bridge.icns
```

on macOS if it does not already exist.

## Recommended clean build workflow

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
./build_app.sh
./build_dmg.sh
```

## Project layout

```text
rf_bridge/config.py       shared defaults
rf_bridge/utils.py        time, safe names, number parsing
rf_bridge/tinysa.py       serial discovery and tinySA command helpers
rf_bridge/export.py       WWB CSV export and latest_scan.csv handling
rf_bridge/scanner.py      scan validation and headless scan loop
rf_bridge/worker.py       threaded tinySA scan worker for the UI
rf_bridge/settings.py     persistent PySide6/QSettings helpers
rf_bridge/ui.py           PySide6 + pyqtgraph UI
rf_bridge/app.py          command-line and packaged-app startup
rf-bridge.py              compatibility launcher
rf-bridge.spec            PyInstaller app bundle spec
build_app.sh              macOS app build helper
build_dmg.sh              macOS DMG build helper
scripts/create_icon.sh    macOS icon generation helper
assets/                   app icon source assets
```

## Notes

v1.9 does not include Apple code signing or notarization. That can come later after the app bundle and DMG flow are stable.

## Mic Plot Markers

Use `Tools > Mic Plot…` to add named frequency markers such as vocal mics, IEMs, comms, or known RF trouble spots. Markers are saved in app settings and appear as labeled vertical lines on the graph.

Current marker fields:

- Visible
- Name
- Frequency MHz
- Color preset

Markers display in Live, Frozen, and Loaded Capture modes.


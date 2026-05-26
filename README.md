# RF Bridge

<p align="center">
  <img src="https://github.com/sweenster247/RF_Bridge/blob/main/assets/%20Logo.png" width="650" alt="RF Bridge Logo">
</p>

<p align="center">
  <strong>tinySA → WWB bridge and live RF visualization utility for macOS</strong>
</p>

<p align="center">
  Lightweight. Offline-first. Built for real-world RF workflows.
</p>

---

## Overview

RF Bridge is a macOS desktop utility for live sound engineers, RF coordinators, and wireless technicians who want lightweight RF visibility using a tinySA spectrum analyzer.

RF Bridge continuously captures scans from a tinySA, exports Wireless Workbench-compatible CSV files, and provides a live RF visualization interface with Mic Plot markers, saved capture loading, freeze trace, and peak hold analysis.

Built with:

- Python
- PySide6
- pyqtgraph
- pyserial
- PyInstaller

---

## Features

### Live RF Visualization

- Real-time RF graphing
- Adjustable refresh intervals
- Peak hold modes
- Freeze Trace mode
- RF summary display with strongest RF hits

### tinySA Integration

- Automatic tinySA detection
- Manual serial port selection
- Connect / Disconnect / Refresh Ports controls
- Frequency range detection

### WWB Workflow Support

- Continuous WWB-compatible CSV export
- Automatic `latest_scan.csv` updating
- Timestamped scan history

### Capture Loading

- Open previously saved RF Bridge CSV scans
- Loaded Capture mode
- Return to Live workflow
- Live scanning can continue while reviewing saved captures

### Mic Plot Markers

- Add named frequency markers for vocals, IEMs, comms, backups, or known RF trouble spots
- Persistent marker storage
- Color-coded vertical marker lines
- User-defined labels displayed directly on the RF graph
- Markers display in Live, Frozen, and Loaded Capture modes

### macOS Application Support

- Packaged `.app` build workflow
- DMG installer workflow
- Release ZIP workflow
- Light / Dark / System appearance modes
- Persistent preferences/settings
- Custom RF Bridge icon assets

---

## Installation

Download the latest release from:

```text
https://github.com/sweenster247/RF_Bridge/releases
```

RF Bridge is currently unsigned. On first launch, macOS may require:

```text
Right-click RF Bridge.app > Open > Open
```

After the first launch, macOS should remember the application.

---

## Building from Source

### Requirements

- macOS
- Python 3.10+
- Homebrew, optional but recommended for DMG creation

### Install Dependencies

```bash
python3 -m pip install -r requirements.txt
```

### Run RF Bridge

Start the desktop UI:

```bash
python3 rf-bridge.py --ui
```

Test packaged-app launch behavior from Terminal:

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

Headless CSV capture still works:

```bash
python3 rf-bridge.py
```

---

## Building Release Artifacts

v1.9.2 adds a consolidated release build script.

Install `create-dmg`:

```bash
brew install create-dmg
```

Build the `.app`, DMG, and zipped app release artifacts:

```bash
./build_release.sh
```

Expected outputs:

```text
dist/releases/RF-Bridge-v1.9.2-macOS-arm64.dmg
dist/releases/RF-Bridge-v1.9.2-macOS-arm64.zip
```

### Build Only the App

```bash
./build_app.sh
```

Output:

```text
dist/RF Bridge.app
```

### Build Only the DMG

After building the app:

```bash
./build_dmg.sh
```

Output:

```text
dist/releases/RF-Bridge-v1.9.2-macOS-arm64.dmg
```

---

## App Launch Flow

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

For example:

```text
~/Documents/RF Bridge/wwb_scans/blues_fest
```

---

## Loading Saved Captures

Open a previous RF Bridge CSV scan from:

```text
File > Open Capture…
```

Supported files use the same two-column RF Bridge / WWB-friendly format:

```text
frequency_mhz, dbm
```

When a capture is loaded, the graph enters **Loaded Capture** mode. Use:

```text
File > Return to Live
```

or the **Return to Live** button to resume the live trace.

---

## Mic Plot Markers

Use:

```text
Tools > Mic Plot…
```

to add named frequency markers such as:

```text
Vocal 1
Vocal 2
IEM A
Comms
Backup HH
```

Markers are saved in app settings and appear as labeled vertical lines on the graph.

---

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

---

## App Icon

v1.9.2 uses the RF Bridge logo artwork as the source for the packaged macOS app icon.

Included assets:

```text
assets/Logo.png
assets/rf-bridge-icon-1024.png
assets/rf-bridge-icon.svg
scripts/create_icon.sh
```

`build_app.sh` and `build_release.sh` automatically create:

```text
assets/rf-bridge.icns
```

on macOS if it does not already exist.

---

## Project Structure

```text
rf_bridge/config.py       shared defaults
rf_bridge/utils.py        time, safe names, number parsing
rf_bridge/tinysa.py       serial discovery and tinySA command helpers
rf_bridge/export.py       WWB CSV export and latest_scan.csv handling
rf_bridge/scanner.py      scan validation and headless scan loop
rf_bridge/worker.py       threaded tinySA scan worker for the UI
rf_bridge/settings.py     persistent PySide6/QSettings helpers
rf_bridge/capture.py      saved capture loading helpers
rf_bridge/micplot.py      Mic Plot marker model/storage helpers
rf_bridge/ui.py           PySide6 + pyqtgraph UI
rf_bridge/app.py          command-line and packaged-app startup
rf_bridge/version.py      app version metadata
rf-bridge.py              compatibility launcher
rf-bridge.spec            PyInstaller app bundle spec
build_app.sh              app-only build helper
build_dmg.sh              DMG-only build helper
build_release.sh          app + DMG + ZIP release build helper
scripts/create_icon.sh    macOS icon generation helper
assets/                   logo and app icon source assets
```

---

## Current Release

### RF Bridge v1.9.2

- Updated app icon source to the RF Bridge logo artwork
- Added consolidated release build script
- Standardized release artifact names:
  - `RF-Bridge-v{version}-macOS-arm64.dmg`
  - `RF-Bridge-v{version}-macOS-arm64.zip`
- Improved Mic Plot label placement and readability from v1.9.1

---

## Planned Features

- Multi-trace overlays
- User-selectable trace colors
- Signed/notarized macOS builds
- Expanded RF analysis tools
- Additional RF device support

---

## License

MIT License

---

## Acknowledgements

Built for live sound engineers, RF coordinators, and anyone tired of everything being a subscription these days.

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

RF Bridge is a macOS desktop utility for live sound engineers, RF coordinators, and wireless technicians using a tinySA spectrum analyzer. It captures live RF scans, visualizes the spectrum in real time, and continuously writes Wireless Workbench-compatible CSV files for practical coordination workflows.

## What’s New in v1.9.5.16

- Added more realistic Demo Mode noise, floor movement, and short transient spikes
- Refined the macOS app icon so the RF Bridge artwork fills more of the icon without the extra outer border
- Added visual-only Demo Mode to the device dropdown
- Demo Mode simulates RF activity without writing CSV files or touching `wwb_scans`
- Cleaned raw tinySA console echoes from the device label
- Simplified connection actions so connected state shows a single Disconnect button
- Cleaned up the tinySA connection panel and added an in-panel silent-device notice
- Simplified the RF plot left-axis label to remove stray clipped lettering
- Added a conservative tinySA wake sequence before the first `version` command
- Removed blocking prompt reads and serial flushes from tinySA command handling
- Added a serial write timeout so USB serial stalls error instead of hanging
- Added a tinySA command fallback using the standalone diagnostic read strategy
- Fixed a UI startup regression that stopped auto-connect before the scan worker started
- Restored the confirmed-working tinySA prompt-based serial read path from v1.9.4.10
- Kept `--debug-serial` TX/RX logging from v1.9.5.7
- Hard-locked scan reads to `data 1`
- Preserved the v1.9.5 sidebar/logo/layout polish
- Kept graph axis/cursor stability fixes and overlay toggle fixes

## Features

### Live RF Visualization
- Real-time RF graphing
- Adjustable refresh intervals
- Peak hold modes
- Freeze Trace mode
- RF summary display

### tinySA Integration
- Automatic tinySA detection
- Manual port selection
- Connect/disconnect controls
- Frequency range detection

### WWB Workflow Support
- Continuous WWB-compatible CSV export
- Automatic `latest_scan.csv` updating
- Timestamped scan history

### Capture Loading and Overlays
- Open a saved RF Bridge CSV capture
- Return to Live workflow
- Load multiple capture overlays
- Toggle overlays on/off from the Overlays menu or top overlay panel

### Markers / Mic Plot
- Add named frequency markers
- Persistent marker storage
- Expanded color-coded vertical marker lines
- Labels displayed directly on the RF graph

### Profiles
- Create a new gig profile during a multi-gig day
- Export the current profile
- Import a saved profile
- Preserve markers, refresh settings, storage/output paths, appearance, and capture overlay references

### macOS Application Support
- Packaged `.app` workflow
- DMG installer workflow
- Light / Dark / System appearance modes
- Persistent preferences/settings
- Consolidated release build script

---

## Installation

Download the latest release from the GitHub Releases page.

RF Bridge is currently unsigned. On first launch:

1. Right-click `RF Bridge.app`
2. Select `Open`
3. Click `Open` again when prompted

After the first launch, macOS should remember the application.

---

## Building from Source

### Requirements

- Python 3.11+
- Homebrew, for DMG creation
- `create-dmg`, for release DMGs

Install dependencies:

```bash
python3 -m pip install -r requirements.txt
```

Dependency monitoring:

- Dependabot is configured to check Python and GitHub Actions dependencies weekly.
- The dependency audit workflow records the exact resolved package versions and fails if `pip-audit` finds a known vulnerability.
- Turn on Dependabot alerts and security updates in the GitHub repository settings to receive vulnerability notifications.

Run from source:

```bash
python3 rf-bridge.py --ui
```

---

## Building a Release

The preferred release command is:

```bash
./build_release.sh
```

This builds the app, creates a DMG, and zips the `.app` bundle.

Output artifacts:

```text
dist/releases/RF-Bridge-v1.9.5.16-macOS-arm64.dmg
dist/releases/RF-Bridge-v1.9.5.16-macOS-arm64.zip
```

Install `create-dmg` if needed:

```bash
brew install create-dmg
```

---

## Project Structure

```text
rf_bridge/
├── app.py
├── capture.py
├── export.py
├── micplot.py
├── scanner.py
├── settings.py
├── tinysa.py
├── ui.py
├── version.py
└── worker.py
```

---

## Planned Features

- More advanced multi-trace overlay controls
- User-selectable overlay colors
- Marker import/export
- Signed/notarized macOS builds
- Expanded RF analysis tools
- Additional RF device support

---

## License

MIT License

---

## Acknowledgements

Built for live sound engineers, RF coordinators, and anyone tired of everything being a subscription these days.


## tinySA Serial Diagnostic

If RF Bridge detects the tinySA but cannot read frequencies, run the standalone diagnostic:

```bash
python3 tinysa_diag.py
```

Or force a specific port:

```bash
python3 tinysa_diag.py --port /dev/cu.usbmodem4001
```

The diagnostic prints raw responses for `version`, `frequencies`, and `data 1` using CR, LF, and CRLF command endings.

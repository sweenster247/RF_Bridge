# RF Bridge

<p align="center">
  <img src="https://github.com/sweenster247/RF_Bridge/blob/main/assets/Logo.png" width="650" alt="RF Bridge Logo">
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

RF Bridge is designed for practical RF workflows in the field, whether you’re coordinating wireless for a Sunday service, festival, corporate event, or theater production.

The goal is simple: get visibility into the RF environment fast. Plug in a tinySA and start understanding the spectrum before the truck doors even open.

## What’s New in v1.9.6.8

- Capture overlays are now grouped into Morning, Afternoon, and Evening sections.
- Each overlay section shows the latest four captures first, with older captures still available from the Overlays menu.
- Auto Trace overlays now follow the same daypart workflow and retain the latest four auto traces per section.
- CSV capture filenames now prioritize RF show-day readability: `Daypart_hh-mmAM_MM-DD_session_device.csv`.
- Graceful tinySA recovery remains included from v1.9.6.7: RF Bridge attempts one automatic reconnect before recommending a device/app restart.

## Features

### Live RF Visualization
- Real-time RF graphing
- Bounded zoom and pan within the current frequency range
- Adjustable refresh intervals
- Peak hold modes
- Freeze Trace mode
- RF summary display with Top RF Hits rounded to practical 0.005 MHz steps

### tinySA Integration
- Automatic tinySA detection
- Manual port selection
- Connect/disconnect controls
- Frequency range detection

### WWB Workflow Support
- Continuous WWB-compatible CSV export
- Automatic `latest_scan.csv` updating
- Timestamped scan history
- Show-day capture names with readable dayparts, for example `Evening_09-15PM_05-27_blue_fest_tinysa4.csv`
- Optional 24-hour capture filename time format in Preferences

### Capture Loading and Overlays
- Open a saved RF Bridge CSV capture
- Return to Live workflow
- Load multiple capture overlays
- Toggle overlays on/off from the Overlays menu or top overlay panel

### Markers / Mic Plot
- Add named frequency markers
- Add and remove markers directly from the RF graph right-click menu
- Persistent marker storage
- Expanded color-coded vertical marker lines
- Staggered labels displayed directly on the RF graph

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

1. Select `Done` on the “RF Bridge” Not Opened prompt.
2. Open `System Settings`.
3. Go to `Privacy & Security`.
4. Scroll to the Security section near the bottom and select `Run Anyway` for RF Bridge.

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
dist/releases/RF-Bridge-v1.9.6.8-macOS-arm64.dmg
dist/releases/RF-Bridge-v1.9.6.8-macOS-arm64.zip
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

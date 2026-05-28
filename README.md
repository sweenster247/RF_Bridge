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

## What’s New in v1.9.9.1

- Combined startup Session Name and Storage Location into one launch dialog.
- Fixed update-check dialog handling and made checks compare against the latest stable GitHub release.
- Added diagnostics export and Copy Debug Info actions under Help.
- Added Open Latest CSV and Reveal Latest CSV actions under File.
- Added scan health details for last scan age, reconnect attempts, mismatch count, and active port.
- Added a collapsible app log and compact RF Summary toggle.
- Added a release checklist script for compile, version, artifact-name, and changelog review.
- Refined Demo Mode custom range controls and Light Mode marker label fills.

## What’s New in v1.9.9

- Added `Help > Check for Updates…` to compare the installed app against the latest GitHub release.
- Tuned Light Mode so panels, plot grid, and readouts feel calmer and less blown out.
- Added a clearer `Auto-detecting...` startup state while tinySA detection runs in the background.
- Slowed Demo Mode random transient spikes and added persistent wide TV-style interference blocks.
- Added click-drag rectangle zoom on the RF graph.
- Hid Mic Plot marker lines and labels when their frequency is outside the zoomed graph window.
- Refined tinySA error messages with more practical reconnect/power-cycle guidance.
- Added release-prep version consistency checks and stronger repo ignore rules for local cache/build files.
- Expanded the in-repo wiki with more field-focused setup and troubleshooting notes.

## What’s New in v1.9.8.1

- Vertical scroll / trackpad wheel gestures now zoom the RF frequency axis.
- Horizontal scroll / trackpad gestures now pan left and right across the active scan range.
- Click-drag the RF graph to zoom into a selected area.
- Zoom and pan stay bounded to the connected tinySA or selected Demo Mode frequency range.
- Double-click the graph to reset back to the full active frequency span.

## What’s New in v1.9.8

- Added a status pill for clearer Disconnected, Connecting, Connected, and Reconnecting states.
- Demo Mode now prompts for a simulated frequency range before connecting.
- Added Demo Mode presets for broadcast UHF and common Shure-style UHF ranges, plus a custom range option.
- Demo Mode now emulates the normal connection flow: Disconnected → range prompt → Connecting → Connected.
- Demo Mode uses the same top-right disconnect button location as tinySA sessions for UI consistency.
- Markers now stay hidden and non-interactive until Demo Mode or a tinySA session is connected.
- Demo scans now adapt their simulated peaks and transient spikes to the selected frequency range.

## Features

### Live RF Visualization
- Real-time RF graphing
- Bounded zoom and pan within the current frequency range
- Adjustable refresh intervals
- Peak hold modes
- Freeze Trace mode
- RF summary display with Top RF Hits rounded to practical 0.005 MHz steps

### Demo Mode
- Prompted Demo Mode startup with selectable frequency ranges
- Broadcast UHF and common Shure-style UHF presets
- Custom demo low/high frequency fields
- Simulated two-second connection state before the demo trace starts
- Demo disconnect control in the same location as the tinySA disconnect control

### tinySA Integration
- Automatic tinySA detection
- Manual port selection
- Connect/disconnect controls
- Frequency range detection

### WWB Workflow Support
- Continuous WWB-compatible CSV export
- Automatic `latest_scan.csv` updating
- Timestamped scan history
- Show-day capture names with readable dayparts, for example `2026-05-27_Evening_09-15PM_blue_fest_tinysa4.csv`
- Optional 24-hour capture filename time format in Preferences

### Capture Loading and Overlays
- Open a saved RF Bridge CSV capture
- Return to Live workflow
- Load multiple capture overlays
- Toggle overlays on/off from the Overlays menu or top overlay panel

### Markers / Mic Plot
- Add named frequency markers
- Add and remove markers directly from the RF graph right-click menu
- Drag marker lines directly on the graph to fine-tune frequencies
- Persistent marker storage
- Expanded color-coded vertical marker lines
- Staggered labels displayed directly on the RF graph
- Markers remain hidden until a live tinySA session or Demo Mode is connected

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
- Manual update check from the Help menu
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
dist/releases/RF-Bridge-v1.9.9.1-macOS-arm64.dmg
dist/releases/RF-Bridge-v1.9.9.1-macOS-arm64.zip
```

Install `create-dmg` if needed:

```bash
brew install create-dmg
```

Before packaging a release, verify the version metadata is aligned:

```bash
python3 scripts/check_version_consistency.py
```

To run the local release checklist:

```bash
python3 scripts/release_checklist.py
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

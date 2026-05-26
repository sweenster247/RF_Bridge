# RF Bridge Wiki

Welcome to the RF Bridge documentation starter page.

## Quick Start

1. Connect a tinySA to your Mac.
2. Open RF Bridge.
3. Enter a gig/session name.
4. Choose a storage location. The default is `~/Documents/RF Bridge`.
5. Confirm the tinySA is connected in the top connection panel.
6. Use `latest_scan.csv` from the gig folder for Wireless Workbench workflows.

## Core Workflows

### Live Scan
RF Bridge reads frequency and amplitude data from the tinySA, displays it in the live graph, and periodically saves WWB-compatible CSV files.

### Markers / Mic Plot
Use `Tools > Markers / Mic Plot…` to add named frequency markers such as Vocal 1, Vocal 2, Guitar RF, or IEM A.

### Capture Loading
Use `File > Open Capture…` to review a previously saved RF Bridge CSV file. Use `Return to Live` to return to the active scan.

### Capture Overlays
Use `File > Open Capture Overlay(s)…` to load one or more saved CSV captures over the current live or loaded trace. Use the `Overlays` menu to show or hide each overlay.

### Profiles
Use the `Profiles` menu for multi-gig days:

- `New Gig Profile…` switches to a new gig/session output folder.
- `Export Current Profile…` saves markers, output folder, appearance, refresh settings, and overlay references.
- `Import Profile…` restores a saved RF Bridge profile.

## Troubleshooting

### tinySA does not auto-connect
Use `Refresh Ports`, select the tinySA port, then click `Connect`. If the tinySA returns no frequency points, verify a sweep range is configured on the device.

### macOS blocks the app
RF Bridge is currently unsigned. Right-click the app and choose `Open` on first launch.

### DMG build fails
Install create-dmg:

```bash
brew install create-dmg
```

Then run:

```bash
./build_release.sh
```

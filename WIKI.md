# RF Bridge Wiki

RF Bridge is a tinySA-to-Wireless Workbench bridge for live RF scanning, show-day capture history, and quick visual comparison of RF conditions.

## Quick Start

1. Connect a tinySA to your Mac.
2. Open RF Bridge.
3. Enter a Session Name and confirm the Storage Location. The default is `~/Documents/RF Bridge`.
4. Wait for `Auto-detecting...` to finish, or select Demo Mode / a serial port manually.
5. Confirm the connection panel shows `Connected`.
6. Use `latest_scan.csv` from the session folder in Wireless Workbench.

## macOS Gatekeeper

RF Bridge is currently unsigned. On first launch:

1. Select `Done` on the “RF Bridge” Not Opened prompt.
2. Open `System Settings`.
3. Go to `Privacy & Security`.
4. Scroll to the Security section near the bottom and select `Run Anyway` for RF Bridge.

After the first launch, macOS should remember the app.

## tinySA Setup

- Use a known-good USB cable that supports data, not charge-only.
- Configure the desired sweep range on the tinySA before relying on live scan data.
- If RF Bridge reports no scan data, check the tinySA sweep range and power-cycle the tinySA.
- If macOS re-enumerates the device under a new serial path, RF Bridge will attempt one reconnect during live scanning.

## Live Scan

RF Bridge reads frequency and amplitude data from the tinySA, displays it on the live RF graph, and periodically writes Wireless Workbench-compatible CSV files.

- Scroll vertically / trackpad wheel to zoom the frequency axis.
- Scroll horizontally / trackpad sideways to pan within the active scan range.
- Click-drag the RF graph to draw a zoom box around a selected frequency area.
- Double-click the graph to reset the full frequency view.
- Use Freeze to pause the visual trace without changing the saved scan workflow.
- Use Peak modes to spot transient RF hits over time.

## Wireless Workbench Workflow

RF Bridge writes:

- `latest_scan.csv`, which is continuously replaced for WWB import.
- Timestamped captures for show-day history.

Recommended workflow:

1. Point WWB at `latest_scan.csv` for current RF conditions.
2. Keep RF Bridge running while scanning throughout the day.
3. Use timestamped captures for morning / afternoon / evening comparison.
4. Load key captures as overlays when comparing environmental changes.

## Demo Mode

Demo Mode is visual only. It does not write CSV files.

Use Demo Mode when:

- You want to test the UI without hardware.
- tinySA is not nearby.
- You need to verify marker, overlay, zoom, or light/dark appearance behavior.

Demo Mode supports built-in UHF presets and a custom frequency range. Its simulated trace includes a low RF floor, a few wireless-style carriers, slower random transient spikes, and persistent wide TV-style interference blocks.

## Capture Overlays

Use `File > Open Capture Overlay(s)...` or the top Capture Overlays panel to load saved CSV captures.

RF Bridge groups overlay controls by daypart when capture filenames include Morning, Afternoon, Evening, or Overnight. This is useful for all-day scanning:

- Morning: baseline RF before the room gets busy.
- Afternoon: production setup / before doors.
- Evening: show conditions.
- Overnight: late-night or cleanup checks.

## Markers / Mic Plot

Use `Tools > Markers / Mic Plot...` to add named frequency markers such as Vocal 1, Vocal 2, Guitar RF, or IEM A.

Marker tips:

- Right-click the graph to add or remove markers at a frequency.
- Drag marker lines or labels to fine-tune frequency placement.
- Marker labels stagger vertically when frequencies are dense.
- Marker lines and labels hide when their frequency is outside the current zoomed graph window.
- Markers stay hidden until a tinySA session or Demo Mode is active.

## Profiles

Use the Profiles menu for multi-gig days:

- `New Gig Profile...` switches to a new session output folder.
- `Export Current Profile...` saves markers, output folder, appearance, refresh settings, and overlay references.
- `Import Profile...` restores a saved RF Bridge profile.

## Updates

Use `Help > Check for Updates...` to compare the installed RF Bridge version with the latest GitHub release.

RF Bridge does not auto-update. The update check ignores prereleases, compares against the latest stable GitHub release, and opens the release page so you can download and install the package manually.

## Diagnostics

Use `Help > Copy Debug Info` when sharing support details. It includes app version, macOS version, selected/active port, detected ports, scan health counters, and recent log lines.

Use `Help > Export Diagnostics...` to save the same information to a text file.

Use `File > Open Latest CSV` or `File > Reveal Latest CSV` to inspect the current Wireless Workbench export.

## Troubleshooting

### tinySA does not auto-connect

Use `Refresh`, select the tinySA port, then click `Connect`. If the tinySA still does not connect, unplug/replug or power-cycle it and try again.

### tinySA connects but no scan data appears

Check the tinySA sweep range. RF Bridge needs frequency points from the device before it can plot or save scan data.

### tinySA stops responding mid-session

RF Bridge attempts one automatic reconnect. If reconnect fails, unplug/replug or power-cycle the tinySA, then click `Connect` again.

### The app opens in Demo Mode first

That is expected when no tinySA is ready yet. Demo Mode stays available while RF Bridge looks for a tinySA in the background.

### macOS blocks the app

Follow the Gatekeeper steps above. This is expected for unsigned builds.

### DMG build fails

Install create-dmg:

```bash
brew install create-dmg
```

Then run:

```bash
./build_release.sh
```

Before packaging, verify version metadata:

```bash
python3 scripts/check_version_consistency.py
```

Or run the broader local release checklist:

```bash
python3 scripts/release_checklist.py
```

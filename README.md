# RF Bridge v1.5.1

RF Bridge connects a tinySA to a Wireless Workbench-friendly CSV workflow with a live desktop RF display.

v1.5.1 is a patch release for the v1.5 operational-readiness build. It keeps the new PySide6/pyqtgraph app workflow and fixes a Qt thread-safety issue that could cause timer warnings and UI crashes after launch.

## Install dependencies

```bash
python3 -m pip install -r requirements.txt
```

## Run

Start the desktop UI:

```bash
python3 rf-bridge.py --ui
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

## v1.5.1 patch fix

- Fixed Qt thread-safety issue in the PySide6 UI
- Routed worker-thread updates through Qt signals/queued UI calls
- Prevented log updates from touching UI widgets from the scan worker thread
- Prevented refresh/disconnect/shutdown behavior from crossing thread boundaries unsafely
- Resolved `QBasicTimer::start: Timers cannot be started from another thread`
- Resolved crash risk from `QObject: Cannot create children for a parent that is in a different thread`

## v1.5 features retained

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
- PyInstaller packaging prep

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
rf_bridge/app.py       command-line app startup
rf-bridge.py           compatibility launcher
```

## Build macOS app bundle

A basic PyInstaller spec and shell helper are included:

```bash
python3 -m pip install pyinstaller
./build_app.sh
```

The unsigned app bundle should land in:

```text
dist/RF Bridge.app
```

Signing and notarization are not included yet.

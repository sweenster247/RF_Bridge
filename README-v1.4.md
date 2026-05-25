# RF Bridge v1.4

RF Bridge v1.4 replaces the Matplotlib UI with a PySide6 + pyqtgraph interface while preserving the v1.3 app-ready module structure.

## Run

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

Set initial refresh:

```bash
python3 rf-bridge.py --ui --refresh 1
```

Headless CSV capture still works:

```bash
python3 rf-bridge.py
```

## Install dependencies

```bash
python3 -m pip install -r requirements.txt
```

## v1.4 layout

```text
rf_bridge/config.py   shared defaults
rf_bridge/utils.py    time, safe names, number parsing
rf_bridge/tinysa.py   serial discovery and tinySA command helpers
rf_bridge/export.py   WWB CSV export and latest_scan.csv handling
rf_bridge/scanner.py  scan validation and headless scan loop
rf_bridge/ui.py       PySide6 + pyqtgraph UI
rf_bridge/app.py      command-line app startup
rf-bridge.py          compatibility launcher
```

## What changed in v1.4

- Replaced Matplotlib UI with PySide6 windowing
- Replaced Matplotlib plotting with pyqtgraph
- Kept live RF graph behavior
- Kept peak hold modes
- Kept refresh cycling
- Kept RF summary / Top 8 RF hits panel
- Kept bottom status bar
- Kept WWB CSV export behavior
- Preserved CLI flags from v1.3

## Why this matters

v1.4 moves RF Bridge closer to a real desktop app. PySide6 gives us a native application window, better layout control, cleaner buttons, and a better foundation for packaging as a clickable `.app` in a future release.

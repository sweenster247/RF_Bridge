# RF Bridge v1.3

RF Bridge v1.3 is a cleanup/refactor release. It keeps the v1.2 behavior but breaks the single script into app-ready modules.

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

## Install dependencies

```bash
python3 -m pip install -r requirements.txt
```

## v1.3 layout

```text
rf_bridge/config.py   shared defaults
rf_bridge/utils.py    time, safe names, number parsing
rf_bridge/tinysa.py   serial discovery and tinySA command helpers
rf_bridge/export.py   WWB CSV export and latest_scan.csv handling
rf_bridge/scanner.py  scan validation and headless scan loop
rf_bridge/ui.py       current Matplotlib UI
rf_bridge/app.py      command-line app startup
rf-bridge.py          compatibility launcher
```

## Why this matters

This version creates the seams needed for a future packaged app. The next app-style step is replacing `rf_bridge/ui.py` with a native window using PySide6/PyQtGraph while leaving the tinySA, scanner, and export logic alone.

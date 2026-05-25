# RF Bridge v1.5.1

v1.5.1 is a stability patch for the v1.5 operational-readiness release.

This update fixes a Qt thread-safety issue in the PySide6 UI that could cause repeated timer warnings and a segmentation fault shortly after launch. Worker-thread events are now routed through Qt-safe UI calls/signals so logging, refresh behavior, disconnects, and shutdown actions stay on the correct thread.

## Fixed

- Fixed `QBasicTimer::start: Timers cannot be started from another thread`
- Fixed crash risk from `QObject: Cannot create children for a parent that is in a different thread`
- Prevented scan-worker callbacks from updating UI widgets directly
- Improved connect/disconnect stability in the PySide6 app workflow

## Retained from v1.5

- Threaded tinySA scan worker
- Connection panel with Refresh Ports, Connect, and Disconnect controls
- Device status/version/range display
- In-app event log
- Freeze Trace mode
- Persistent settings
- WWB CSV export and `latest_scan.csv`
- PyInstaller packaging prep

## Run

```bash
python3 rf-bridge.py --ui
```

# RF Bridge v1.8 — Saved Capture Loading

RF Bridge v1.8 adds the first saved-capture workflow, allowing previous RF Bridge CSV scans to be opened and reviewed directly in the app.

## Added

- `File > Open Capture…` menu action
- Loaded Capture mode for offline scan review
- Return to Live menu action
- Return to Live side-panel button
- CSV capture loader for RF Bridge / WWB-style two-column scan files
- Internal capture-loading structure designed to support future overlays

## Retained

- Packaged macOS app workflow
- DMG build workflow
- Preferences window
- System / Dark / Light appearance options
- tinySA auto-detection
- Connect / Disconnect / Refresh Ports controls
- Live RF graph
- Freeze Trace
- Peak hold modes
- WWB-compatible CSV export
- `latest_scan.csv` updating

## Notes

This release intentionally keeps capture loading simple: one saved CSV capture at a time. Future versions can build on this foundation with multiple overlays, user-selectable trace colors, capture toggles, and comparison workflows.

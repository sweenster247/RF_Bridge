# RF Bridge v1.9 — Mic Plot Markers

RF Bridge v1.9 adds a basic Mic Plot workflow for manually placing labeled wireless frequencies on the RF graph.

This release keeps the feature intentionally lightweight: manual markers first, import/export and advanced overlays later.

## Added

### Mic Plot
- Added `Tools > Mic Plot…`
- Add, edit, and remove named frequency markers
- Enter marker frequency in MHz
- Toggle marker visibility
- Choose from preset marker colors
- Display markers as labeled vertical lines on the RF graph
- Persist markers between launches using app settings

### Display Behavior
- Mic plot markers display in Live mode
- Mic plot markers remain visible during Frozen traces
- Mic plot markers display while reviewing Loaded Captures

## Existing Features Retained
- Packaged macOS `.app` workflow
- DMG build support
- tinySA auto-detection
- Connect/disconnect controls
- Real-time RF graph
- Freeze Trace
- Peak hold modes
- Capture loading
- WWB-compatible CSV export
- Persistent preferences
- Light/Dark/System appearance modes

## Notes

v1.9 focuses on manual frequency plotting. Future releases may add marker import/export, WWB coordination list support, multi-trace overlays, and user-selectable overlay colors.

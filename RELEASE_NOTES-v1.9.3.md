# RF Bridge v1.9.3 — tinySA Startup Fix

RF Bridge v1.9.3 is a small bug-fix release focused on restoring reliable startup auto-connect behavior for tinySA devices.

## Fixed

- Fixed an issue where RF Bridge could show `The tinySA returned no frequency points` during startup even when the tinySA was connected
- Added retry handling when reading the tinySA frequency range immediately after opening the serial connection
- Delayed packaged-app auto-connect slightly so the main window and serial device have time to settle before scanning begins

## Retained

- Mic Plot markers from v1.9
- Improved Mic Plot label visibility from v1.9.1
- Logo-based app icon and consolidated release build workflow from v1.9.2
- Capture loading
- Live RF visualization
- Freeze Trace
- Peak hold modes
- WWB-compatible CSV export
- Light/Dark/System appearance modes

## Notes

This release is recommended for anyone using RF Bridge as a packaged macOS app with automatic tinySA connection on launch.

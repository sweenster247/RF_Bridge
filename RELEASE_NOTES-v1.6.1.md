# RF Bridge v1.6.1

RF Bridge v1.6.1 is a packaging-focused patch release for the first macOS app build.

## Fixed
- Fixed packaged macOS app launch behavior where the app could prompt for a gig/session name and then appear to do nothing.
- Deferred tinySA auto-detection/connect until after the main PySide6 window is visible and the Qt event loop is running.
- Changed packaged app default scan output location to `~/Documents/RF Bridge/wwb_scans/<gig>` instead of a relative working directory.

## Notes
- The normal script workflow remains unchanged:

```bash
python3 rf-bridge.py --ui
```

- Rebuild the macOS app with:

```bash
./build_app.sh
```

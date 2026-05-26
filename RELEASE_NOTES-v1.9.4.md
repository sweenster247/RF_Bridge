# RF Bridge v1.9.4 — Profiles, Overlays, and Help Menu

RF Bridge v1.9.4 adds practical workflow improvements aimed at multi-gig days and offline RF review.

## Added

### Profiles
- New gig profile workflow
- Export current profile to `.rfbridge-profile.json`
- Import saved RF Bridge profiles
- Profiles preserve markers, storage/output paths, refresh settings, appearance, and overlay references

### Capture Overlays
- Load multiple saved RF Bridge CSV captures as overlays
- Toggle each overlay on/off from the Overlays menu
- Clear all overlays when needed

### Help/About
- Added About RF Bridge menu item
- Added RF Bridge Wiki menu item
- Added Open Scan Folder helper
- Added starter `WIKI.md`

## Fixed / Improved
- Failed startup auto-connect attempts now log cleanly instead of blocking app launch
- App can open first and let the user connect when the tinySA is ready
- PyInstaller spec now avoids bundling several unused Qt modules to help control app size

## Notes

This release keeps the v1.9 marker/mic-plot workflow and v1.9.3 tinySA startup fixes while adding profile and overlay groundwork that will support future v2 coordination features.

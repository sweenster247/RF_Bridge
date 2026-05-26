# RF Bridge v1.9.4.4

Patch release for packaged macOS app startup handling.

## Fixed
- Fixed a regression where the packaged app could prompt for a gig name and then exit before showing the main window.
- Prevented Qt startup dialogs from leaving a pending application quit event before the main UI launches.

## Retained
- Cleaner shutdown handling from v1.9.4.2.
- v1.9.4 profile, overlay, marker, and Help/About features.

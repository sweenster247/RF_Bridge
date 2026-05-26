# RF Bridge v1.9.4.7

Patch release focused on tinySA startup reliability.

## Fixed
- Added fallback frequency-axis generation when tinySA returns scan data but no frequency table on startup.
- Reduced blocking startup failures caused by transient empty `frequencies` responses.
- Kept the UI usable for overlays and manual reconnect when tinySA is slow to initialize.

## Notes
The primary path still uses the tinySA `frequencies` command. The fallback only activates when scan data is available but the frequency list is empty.

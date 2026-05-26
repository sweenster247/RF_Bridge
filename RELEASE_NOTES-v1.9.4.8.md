# RF Bridge v1.9.4.8 — tinySA Serial Startup Revert

This patch restores the known-good v1.8-style tinySA frequency read path while retaining the v1.9.4 UI, profile, overlay, and shutdown improvements.

## Fixed
- Restored simple tinySA startup communication flow:
  - open serial port
  - wait briefly
  - read `version`
  - read `frequencies`
  - start scanning
- Removed the v1.9.4.x frequency fallback/probing behavior that could leave some tinySA units returning empty frequency lists.
- Kept app UI open and recoverable if tinySA is not ready.

## Notes
If this patch still reports no frequency points, the next diagnostic step is to verify the tinySA command output directly with a minimal serial test outside the full RF Bridge UI.

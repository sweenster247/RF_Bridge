# RF Bridge v1.9.5.9

## Fixed
- Fixed a UI auto-connect regression introduced while adding serial debug plumbing.
- The app now stores `debug_serial` on the main window before creating the scan worker.

## Notes
This preserves the v1.9.5.8 restored tinySA prompt-based serial read path.

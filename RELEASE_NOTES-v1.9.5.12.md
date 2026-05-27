# RF Bridge v1.9.5.12

## Added
- Added a conservative tinySA wake sequence before RF Bridge reads `version` or frequencies.
- The wake sequence sends blank lines, `resume`, `release`, and `refresh` using bounded reads.

## Notes
This does not replace a full tinySA reboot when the device console is completely wedged, but it gives RF Bridge one safe recovery pass before reporting a silent device.

# RF Bridge v1.9.4.10

## Fixed
- Improved tinySA4 startup connection reliability.
- RF Bridge now waits 5 seconds after opening the serial port before sending `version`, `frequencies`, or `data 1`.
- Increased serial timeout to better match real tinySA4 response behavior observed in diagnostics.

## Notes
The diagnostic script confirmed that the tinySA4 USB device can appear immediately while the command console is not yet ready. Waiting longer before first command restored valid responses for `version`, `frequencies`, and `data 1`.

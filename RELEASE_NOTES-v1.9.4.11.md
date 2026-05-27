# RF Bridge v1.9.4.11

RF Bridge v1.9.4.11 is a UI stability patch based on the confirmed-working v1.9.4.10 tinySA connection path.

## Fixed

- Fixed a graph resizing issue triggered by vertical mouse movement across the RF plot.
- Kept the dBm vertical scale fixed when tinySA connects and the first live scan renders.
- Prevented cursor, threshold, mic marker, and Top 8 guide lines from influencing plot auto-ranging.
- Constrained the hover readout panel height so the main window layout remains stable.
- Fixed capture overlay show/hide crashes when detoggling overlays from the panel or menu.
- Overlay controls now sync state without rebuilding the active Qt widget during signal handling.

## Notes

This patch intentionally preserves the v1.9.4.10 tinySA startup behavior that was confirmed working.

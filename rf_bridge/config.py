"""Shared RF Bridge defaults."""

BAUD = 115200
SCAN_INTERVAL_SECONDS = 300
UI_UPDATE_SECONDS = 2

# tinySA4 may expose USB metadata before its command console is ready.
TINYSA_STARTUP_SETTLE_SECONDS = 5.0
TINYSA_SERIAL_TIMEOUT_SECONDS = 5

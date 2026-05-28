"""Scan validation and non-UI scan loop."""

import time

from .config import SCAN_INTERVAL_SECONDS
from .export import save_wwb_csv
from .tinysa import send_command
from .utils import parse_numbers, time_12h


def validate_frequency_list(freqs_mhz):
    if not freqs_mhz:
        raise RuntimeError(
            "The tinySA returned no frequency points. "
            "Make sure a sweep range is configured on the device, then rerun RF Bridge."
        )


def read_frequencies_mhz(ser, debug_log=None):
    """Read the tinySA frequency table using the proven v1.8 path.

    v1.9.4.x added retries/fallback sweep probing around startup. On some
    tinySA units that made the serial console less reliable. This intentionally
    restores the simple command flow that was known-good in v1.8/v1.9.2.
    """
    freqs_hz = parse_numbers(
        send_command(
            ser,
            "frequencies",
            debug_log=debug_log,
        )
    )

    freqs_mhz = [
        f / 1_000_000
        for f in freqs_hz
    ]

    validate_frequency_list(freqs_mhz)

    return freqs_mhz


def read_scan_dbm(ser, debug_log=None):
    values = parse_numbers(
        send_command(ser, "data 1", debug_log=debug_log)
    )

    if not values:
        raise RuntimeError("The tinySA returned no scan data.")

    return values


def run_headless(ser, output_dir, gig_slug, freqs_mhz):
    while True:
        dbm = read_scan_dbm(ser)

        print("=" * 50)

        print(
            f"Captured {len(dbm)} scan points at "
            f"{time_12h()}"
        )

        save_wwb_csv(
            output_dir,
            gig_slug,
            freqs_mhz,
            dbm,
            "tinySA"
        )

        time.sleep(SCAN_INTERVAL_SECONDS)

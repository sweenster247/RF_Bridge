"""Saved RF Bridge capture loading."""

import csv
import os


def load_capture_csv(path):
    """Load an RF Bridge / WWB-style two-column CSV capture.

    Expected rows are frequency_mhz, dbm with no header. Blank rows and
    malformed rows are ignored so older or hand-edited captures do not crash
    the UI.
    """
    freqs_mhz = []
    dbm = []

    with open(path, "r", newline="") as file:
        reader = csv.reader(file)
        for row in reader:
            if len(row) < 2:
                continue
            try:
                freq = float(row[0])
                level = float(row[1])
            except (TypeError, ValueError):
                continue
            freqs_mhz.append(freq)
            dbm.append(level)

    if not freqs_mhz or not dbm:
        raise RuntimeError("No capture data was found in the selected CSV file.")

    if len(freqs_mhz) != len(dbm):
        raise RuntimeError("Capture frequency and level counts do not match.")

    return {
        "name": os.path.basename(path),
        "path": path,
        "freqs_mhz": freqs_mhz,
        "dbm": dbm,
    }

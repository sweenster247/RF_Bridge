"""Wireless Workbench CSV export helpers."""

import csv
import os
from datetime import datetime, time

from .utils import safe_name


def capture_daypart(captured_at):
    """Return a readable, capitalized daypart for show-day RF sweep filenames."""
    capture_time = captured_at.time()
    if time(5, 0) <= capture_time < time(12, 0):
        return "Morning"
    if time(12, 0) <= capture_time < time(17, 0):
        return "Afternoon"
    if time(17, 0) <= capture_time <= time(23, 59, 59):
        return "Evening"
    return "Overnight"


def save_wwb_csv(output_dir, gig_slug, freqs_mhz, dbm, device_name="tinySA", filename_time_format="12h"):
    captured_at = datetime.now()
    date_stamp = captured_at.strftime("%Y-%m-%d")
    if filename_time_format == "24h":
        time_stamp = captured_at.strftime("%H-%M")
    else:
        time_stamp = captured_at.strftime("%I-%M%p")
    daypart = capture_daypart(captured_at)
    device_slug = safe_name(device_name or "tinySA")

    filename = os.path.join(
        output_dir,
        f"{date_stamp}_{daypart}_{time_stamp}_{gig_slug}_{device_slug}.csv"
    )

    latest_filename = os.path.join(
        output_dir,
        "latest_scan.csv"
    )

    rows = [
        [
            f"{f:.6f}",
            f"{level:.2f}",
        ]
        for f, level in zip(freqs_mhz, dbm)
    ]

    with open(filename, "w", newline="\r\n") as file:
        writer = csv.writer(file)
        writer.writerows(rows)

    latest_temp = f"{latest_filename}.tmp"
    with open(latest_temp, "w", newline="\r\n") as file:
        writer = csv.writer(file)
        writer.writerows(rows)
    os.replace(latest_temp, latest_filename)

    print(f"Saved:  {filename}")
    print(f"Latest: {latest_filename}")

    return filename, latest_filename

"""Wireless Workbench CSV export helpers."""

import csv
import os
from datetime import datetime

from .utils import safe_name


def save_wwb_csv(output_dir, gig_slug, freqs_mhz, dbm, device_name="tinySA"):
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    device_slug = safe_name(device_name or "tinySA")

    filename = os.path.join(
        output_dir,
        f"{timestamp}_{gig_slug}_{device_slug}.csv"
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

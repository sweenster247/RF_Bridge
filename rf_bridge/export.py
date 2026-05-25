"""Wireless Workbench CSV export helpers."""

import csv
import os
import shutil
from datetime import datetime


def save_wwb_csv(output_dir, gig_slug, freqs_mhz, dbm):
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    filename = os.path.join(
        output_dir,
        f"{gig_slug}_tinysa_scan_{timestamp}.csv"
    )

    latest_filename = os.path.join(
        output_dir,
        "latest_scan.csv"
    )

    with open(filename, "w", newline="\r\n") as file:
        writer = csv.writer(file)

        for f, level in zip(freqs_mhz, dbm):
            writer.writerow([
                f"{f:.6f}",
                f"{level:.2f}"
            ])

    shutil.copyfile(filename, latest_filename)

    print(f"Saved:  {filename}")
    print(f"Latest: {latest_filename}")

    return filename, latest_filename

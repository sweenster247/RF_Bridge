"""Command-line startup for RF Bridge."""

import argparse
import os
import time

import serial

from .config import BAUD, SCAN_INTERVAL_SECONDS, UI_UPDATE_SECONDS
from .scanner import read_frequencies_mhz, run_headless
from .tinysa import (
    candidate_serial_ports,
    describe_port,
    find_tinysa_port,
    send_command,
)
from .ui import run_ui
from .utils import safe_name


def build_parser():
    parser = argparse.ArgumentParser(
        description="TinySA to WWB RF Bridge"
    )

    parser.add_argument(
        "--ui",
        action="store_true",
        help="Show real-time RF graph"
    )

    parser.add_argument(
        "--port",
        default=None,
        help="Manually choose a serial port if auto-detection is not desired"
    )

    parser.add_argument(
        "--list-ports",
        action="store_true",
        help="List detected serial ports and exit"
    )

    parser.add_argument(
        "--refresh",
        type=float,
        default=UI_UPDATE_SECONDS,
        help="Initial UI refresh interval in seconds. Can also be changed from the UI."
    )

    return parser


def list_ports_and_exit():
    ports = candidate_serial_ports()

    if not ports:
        print("No serial ports found.")
        return

    print("Detected serial ports:")

    for port in ports:
        print(f"  - {describe_port(port)}")


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.list_ports:
        list_ports_and_exit()
        return

    gig_name = input("Gig name: ")
    gig_slug = safe_name(gig_name)

    output_dir = os.path.join(
        "wwb_scans",
        gig_slug
    )

    os.makedirs(
        output_dir,
        exist_ok=True
    )

    if args.ui:
        print(f"Output folder: {output_dir}")
        print(f"Scan interval: {SCAN_INTERVAL_SECONDS} seconds")
        print(f"UI refresh: {args.refresh} seconds")
        print("UI enabled: True")

        run_ui(
            output_dir=output_dir,
            gig_slug=gig_slug,
            ui_update_seconds=args.refresh,
            selected_port=args.port,
        )
        return

    if args.port:
        selected_port = args.port
        version_output = None
        print(f"Using manually selected port: {selected_port}")
    else:
        selected_port, version_output, scanned_ports = find_tinysa_port()

        print("Auto-detected tinySA:")
        print(f"  {selected_port}")

        if version_output:
            print(version_output)

    with serial.Serial(
        selected_port,
        BAUD,
        timeout=2
    ) as ser:

        time.sleep(1)

        if version_output is None:
            version_output = send_command(
                ser,
                "version"
            ).strip()

            print(version_output)

        freqs_mhz = read_frequencies_mhz(ser)

        print(f"Serial port: {selected_port}")
        print(f"Output folder: {output_dir}")
        print(f"Scan interval: {SCAN_INTERVAL_SECONDS} seconds")
        print(f"Frequency range: {min(freqs_mhz):.3f} MHz - {max(freqs_mhz):.3f} MHz")
        print("UI enabled: False")

        run_headless(
            ser,
            output_dir,
            gig_slug,
            freqs_mhz
        )


if __name__ == "__main__":
    main()

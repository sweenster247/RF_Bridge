"""Command-line and packaged-app startup for RF Bridge."""

import argparse
import os
import sys
import time

import serial

from .config import BAUD, SCAN_INTERVAL_SECONDS, UI_UPDATE_SECONDS, TINYSA_SERIAL_TIMEOUT_SECONDS, TINYSA_SERIAL_WRITE_TIMEOUT_SECONDS, TINYSA_STARTUP_SETTLE_SECONDS
from .scanner import read_frequencies_mhz, run_headless
from .tinysa import (
    candidate_serial_ports,
    describe_port,
    find_tinysa_port,
    send_command,
    wake_console,
)
from .settings import AppSettings
from .ui import run_ui
from .utils import clean_tinysa_version, safe_name


def running_as_packaged_app():
    """Return True when launched from a PyInstaller bundle."""
    return bool(getattr(sys, "frozen", False))


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
        "--app",
        action="store_true",
        help="Launch in desktop-app mode without requiring terminal prompts"
    )

    parser.add_argument(
        "--gig",
        default=None,
        help="Gig/session name. Useful for packaged app launches and automation."
    )

    parser.add_argument(
        "--output-dir",
        default=None,
        help="Override output folder. Defaults to wwb_scans/<gig_slug>."
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

    parser.add_argument(
        "--debug-serial",
        action="store_true",
        help="Log detailed tinySA serial TX/RX diagnostics to the app log and terminal."
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


def prompt_gig_name_gui(default_name="RF Bridge Scan"):
    """Prompt for a gig name using Qt when the app is launched without a terminal."""
    from PySide6.QtWidgets import QApplication, QInputDialog

    app = QApplication.instance() or QApplication([])
    # Modal startup prompts run before the main window exists. Disable
    # auto-quit here so closing a prompt does not leave a pending quit
    # event that immediately exits the packaged app when the main UI starts.
    app.setQuitOnLastWindowClosed(False)
    text, ok = QInputDialog.getText(
        None,
        "RF Bridge",
        "Session Name:",
        text="",
    )

    if not ok:
        return None

    return text.strip() or default_name


def default_app_storage_root():
    """Return the default scan storage root for packaged app launches."""
    return os.path.join(
        os.path.expanduser("~"),
        "Documents",
        "RF Bridge",
    )


def prompt_storage_root_gui(default_root=None):
    """Prompt for the app scan storage root using Qt.

    The selected folder becomes the root that contains the app-managed
    wwb_scans/<gig> directory structure.
    """
    from PySide6.QtWidgets import QApplication, QFileDialog

    app = QApplication.instance() or QApplication([])
    # See prompt_gig_name_gui: startup dialogs appear before the main
    # window, so prevent Qt from treating dialog close as application exit.
    app.setQuitOnLastWindowClosed(False)
    default_root = default_root or default_app_storage_root()
    os.makedirs(default_root, exist_ok=True)

    selected = QFileDialog.getExistingDirectory(
        None,
        "Choose RF Bridge Storage Location",
        default_root,
    )

    selected = selected or default_root
    AppSettings().set_storage_root(selected)
    return selected


def resolve_gig_name(args, use_app_mode):
    if args.gig:
        return args.gig

    if use_app_mode:
        return prompt_gig_name_gui()

    return input("Gig name: ")


def resolve_output_dir(args, gig_slug, use_app_mode=False):
    if args.output_dir:
        return args.output_dir

    if use_app_mode:
        settings = AppSettings()
        storage_root = prompt_storage_root_gui(settings.get_storage_root())
        return os.path.join(
            storage_root,
            "wwb_scans",
            gig_slug,
        )

    return os.path.join(
        "wwb_scans",
        gig_slug
    )


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.list_ports:
        list_ports_and_exit()
        return

    use_app_mode = args.app or running_as_packaged_app()

    # A double-clicked macOS bundle has no useful terminal, so it should launch
    # the desktop UI by default. The CLI still keeps the old explicit --ui flow.
    if use_app_mode:
        args.ui = True

    gig_name = resolve_gig_name(args, use_app_mode)
    if gig_name is None:
        return

    gig_slug = safe_name(gig_name)
    output_dir = resolve_output_dir(args, gig_slug, use_app_mode)

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
            debug_serial=args.debug_serial,
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
        timeout=TINYSA_SERIAL_TIMEOUT_SECONDS,
        write_timeout=TINYSA_SERIAL_WRITE_TIMEOUT_SECONDS,
    ) as ser:

        time.sleep(TINYSA_STARTUP_SETTLE_SECONDS)

        if version_output is None:
            wake_console(ser)
            raw_version_output = send_command(
                ser,
                "version"
            ).strip()
            version_output = clean_tinysa_version(raw_version_output)

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

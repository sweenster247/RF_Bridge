"""tinySA serial discovery and command helpers."""

import time

import serial
from serial.tools import list_ports

from .config import BAUD


def send_command(ser, cmd):
    ser.write((cmd + "\r").encode())
    time.sleep(0.2)
    return ser.read_until(b"ch> ").decode(errors="ignore")


def looks_like_tinysa(*values):
    """
    tinySA devices may identify themselves in either the serial `version`
    response or the USB serial metadata exposed by pyserial.
    """
    combined = " ".join(
        str(value or "")
        for value in values
    ).lower()

    return "tinysa" in combined


def candidate_serial_ports():
    """
    Return likely serial devices with Mac-friendly ordering.

    pyserial handles the platform differences for us, so this works better
    than shelling out to `ls /dev/tty.*`.
    """
    ports = list(list_ports.comports())

    def sort_key(port):
        device = port.device.lower()

        # On macOS, /dev/cu.* is usually the better app-facing serial endpoint.
        cu_preference = 0 if "/dev/cu." in device else 1

        # USB modems/adapters are more likely than Bluetooth console devices.
        usb_preference = 0 if ("usb" in device or "modem" in device) else 1

        return (
            cu_preference,
            usb_preference,
            device,
        )

    return sorted(ports, key=sort_key)


def describe_port(port):
    parts = [port.device]

    if port.description:
        parts.append(port.description)

    if port.manufacturer:
        parts.append(port.manufacturer)

    return " — ".join(parts)


def find_tinysa_port(baud=BAUD, timeout=1.5):
    """
    Find the tinySA serial port.

    First trust pyserial USB metadata. Only if metadata is inconclusive do we
    briefly probe ports with the tinySA `version` command.
    """
    ports = candidate_serial_ports()

    if not ports:
        raise RuntimeError(
            "No serial ports were found. Is the tinySA plugged in?"
        )

    scanned = []

    # Fast path: metadata already says tinySA. Do not open the port here.
    for port in ports:
        description = describe_port(port)
        scanned.append(description)

        if looks_like_tinysa(
            port.device,
            port.description,
            port.manufacturer,
            port.product,
            description,
        ):
            return port.device, description, scanned

    # Fallback: metadata did not identify it, so probe each port.
    for port in ports:
        device = port.device

        try:
            with serial.Serial(
                device,
                baud,
                timeout=timeout
            ) as ser:
                time.sleep(0.7)
                ser.reset_input_buffer()

                version_output = send_command(
                    ser,
                    "version"
                )

        except (OSError, serial.SerialException):
            continue

        if looks_like_tinysa(version_output):
            header = version_output.strip() or describe_port(port)
            return device, header, scanned

    scanned_text = "\n".join(
        f"  - {item}"
        for item in scanned
    )

    raise RuntimeError(
        "No tinySA was detected from serial port headers.\n"
        "Scanned ports:\n"
        f"{scanned_text}\n\n"
        "Try forcing it with --port /dev/cu.usbmodem4001."
    )

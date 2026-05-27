"""tinySA serial discovery and command helpers."""

import time

import serial
from serial.tools import list_ports

from .config import BAUD


def send_command(ser, cmd, delay_seconds=0.2, response_window_seconds=5.0, debug_log=None):
    """Send a tinySA console command and return text output.

    v1.9.5.8 restores the confirmed-working v1.9.4.10 prompt-based read path
    while keeping the debug serial logging added in v1.9.5.7.
    """
    if debug_log is not None:
        port = getattr(ser, "port", "unknown")
        is_open = getattr(ser, "is_open", None)
        timeout = getattr(ser, "timeout", None)
        debug_log(f"[serial] CMD {cmd!r} on {port}; open={is_open}; timeout={timeout}")

    payload = (cmd + "\r").encode()
    if debug_log is not None:
        debug_log(f"[serial] TX bytes={payload!r}")

    ser.write(payload)
    time.sleep(delay_seconds)

    response = ser.read_until(b"ch> ", size=None).decode(errors="ignore")
    if debug_log is not None:
        raw = response.encode(errors="replace")
        debug_log(f"[serial] RX bytes={len(raw)}")
        preview = response.replace("\r", "\\r").replace("\n", "\\n")
        if len(preview) > 240:
            preview = preview[:240] + "..."
        debug_log(f"[serial] RX preview={preview!r}")

    return response


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

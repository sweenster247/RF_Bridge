#!/usr/bin/env python3
"""tinySA serial diagnostic helper for RF Bridge.

This intentionally avoids the RF Bridge UI/worker stack and prints raw serial
responses so startup/command issues can be debugged without guessing.
"""

import argparse
import time
from datetime import datetime

import serial
from serial.tools import list_ports

BAUD = 115200
COMMANDS = ["version", "frequencies", "data 1"]


def describe_port(port):
    parts = [port.device]
    if port.description:
        parts.append(port.description)
    if port.manufacturer:
        parts.append(port.manufacturer)
    return " — ".join(parts)


def candidate_ports():
    ports = list(list_ports.comports())

    def sort_key(port):
        device = port.device.lower()
        cu_preference = 0 if "/dev/cu." in device else 1
        usb_preference = 0 if ("usb" in device or "modem" in device) else 1
        return (cu_preference, usb_preference, device)

    return sorted(ports, key=sort_key)


def auto_port():
    ports = candidate_ports()
    for port in ports:
        text = " ".join(str(x or "") for x in [
            port.device,
            port.description,
            port.manufacturer,
            port.product,
            describe_port(port),
        ]).lower()
        if "tinysa" in text:
            return port.device
    if ports:
        return ports[0].device
    raise SystemExit("No serial ports found.")


def read_window(ser, seconds):
    """Collect bytes for a fixed window plus a short idle grace period."""
    end = time.time() + seconds
    idle_deadline = None
    chunks = []

    while time.time() < end:
        waiting = ser.in_waiting
        if waiting:
            chunks.append(ser.read(waiting))
            idle_deadline = time.time() + 0.25
        elif idle_deadline and time.time() >= idle_deadline:
            break
        time.sleep(0.025)

    return b"".join(chunks)


def send_and_capture(ser, command, line_ending, timeout):
    try:
        ser.reset_input_buffer()
    except Exception:
        pass

    payload = (command + line_ending).encode()
    ser.write(payload)
    ser.flush()
    time.sleep(0.2)
    raw = read_window(ser, timeout)
    text = raw.decode(errors="replace")
    numbers = []
    for line in text.splitlines():
        try:
            numbers.append(float(line.strip()))
        except ValueError:
            pass
    return payload, raw, text, numbers


def main():
    parser = argparse.ArgumentParser(description="RF Bridge tinySA serial diagnostic")
    parser.add_argument("--port", default=None, help="Serial port, ex: /dev/cu.usbmodem4001")
    parser.add_argument("--baud", type=int, default=BAUD)
    parser.add_argument("--timeout", type=float, default=3.0)
    parser.add_argument("--settle", type=float, default=2.0, help="Seconds to wait after opening port")
    args = parser.parse_args()

    ports = candidate_ports()
    print("RF Bridge tinySA diagnostic")
    print(f"Started: {datetime.now().isoformat(timespec='seconds')}")
    print("Detected ports:")
    for p in ports:
        print(f"  - {describe_port(p)}")

    port = args.port or auto_port()
    print(f"\nUsing port: {port}")
    print(f"Baud: {args.baud}")
    print(f"Settle: {args.settle}s")
    print(f"Read timeout window: {args.timeout}s")

    with serial.Serial(port, args.baud, timeout=0.25) as ser:
        time.sleep(args.settle)
        for line_ending_name, line_ending in [("CR", "\r"), ("LF", "\n"), ("CRLF", "\r\n")]:
            print("\n" + "=" * 72)
            print(f"Line ending test: {line_ending_name}")
            for command in COMMANDS:
                payload, raw, text, numbers = send_and_capture(
                    ser,
                    command,
                    line_ending,
                    args.timeout,
                )
                print("-" * 72)
                print(f"Command: {command!r} payload={payload!r}")
                print(f"Bytes: {len(raw)}  Numeric lines parsed: {len(numbers)}")
                if numbers:
                    preview = numbers[:5]
                    tail = numbers[-5:] if len(numbers) > 5 else []
                    print(f"Number preview: {preview}")
                    if tail:
                        print(f"Number tail:    {tail}")
                print("Raw repr:")
                print(repr(text[:2000]))


if __name__ == "__main__":
    main()

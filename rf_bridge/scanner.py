"""Scan validation and non-UI scan loop."""

import struct
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


def _debug_binary_response(raw, debug_log):
    if debug_log is None:
        return
    preview = raw[:80]
    debug_log(f"[serial] RX binary bytes={len(raw)} preview={preview!r}")


def send_binary_command(
    ser,
    cmd,
    expected_payload_bytes=None,
    max_seconds=60.0,
    idle_seconds=0.45,
    payload_idle_seconds=8.0,
    progress_callback=None,
    cancel_check=None,
    debug_log=None,
):
    """Send a tinySA command that may return binary data."""
    payload = (cmd + "\r").encode()
    if debug_log is not None:
        debug_log(f"[serial] TX binary command={cmd!r} bytes={payload!r}")
    try:
        ser.reset_input_buffer()
    except Exception:
        pass
    ser.write(payload)

    end_time = time.time() + max_seconds
    idle_deadline = None
    chunks = []
    target_total = None
    if expected_payload_bytes is not None:
        # scanraw is documented as: "{" + ("x" + 2 value bytes) per point + "}".
        target_total = int(expected_payload_bytes)

    while time.time() < end_time:
        if cancel_check is not None and cancel_check():
            break
        waiting = getattr(ser, "in_waiting", 0)
        if waiting:
            chunk = ser.read(waiting)
            chunks.append(chunk)
            raw = b"".join(chunks)
            current_payload = _scanraw_payload_bytes_read(raw)
            if progress_callback is not None and target_total:
                progress_callback(min(current_payload, target_total), target_total)
            if target_total and current_payload >= target_total:
                break
            if not target_total and b"}" in chunk and b"{" in raw:
                break
            if b"ch> " in raw[-32:] and b"{" not in raw:
                break
            if target_total and b"{" in raw and current_payload < target_total:
                idle_deadline = time.time() + payload_idle_seconds
            else:
                idle_deadline = time.time() + idle_seconds
        elif idle_deadline and time.time() >= idle_deadline:
            break
        time.sleep(0.01)

    raw = b"".join(chunks)
    _debug_binary_response(raw, debug_log)
    return raw


def _extract_scanraw_payload(raw):
    start = raw.find(b"{")
    end = raw.rfind(b"}")
    if start < 0:
        return b""
    if end <= start:
        prompt = raw.find(b"ch>", start)
        end = prompt if prompt > start else len(raw)
    return raw[start + 1:end]


def _scanraw_payload_bytes_read(raw):
    start = raw.find(b"{")
    if start < 0:
        return 0
    return max(0, len(raw) - start - 1)


def decode_scanraw_dbm(raw, points, ultra=True):
    expected_bytes = int(points) * 3
    start = raw.find(b"{")
    if start < 0:
        raise RuntimeError("tinySA scanraw response did not contain a payload start marker.")
    payload = raw[start + 1:start + 1 + expected_bytes]
    if len(payload) < expected_bytes:
        raise RuntimeError(
            f"tinySA scanraw returned {len(payload)} payload bytes; expected {expected_bytes}."
        )
    values = []
    offset = 174 if ultra else 128
    for index in range(0, expected_bytes, 3):
        value = struct.unpack("<H", payload[index + 1:index + 3])[0]
        values.append((value / 32.0) - offset)
    return values


def configure_scan_profile(ser, profile, debug_log=None):
    """Apply RF Bridge's scan profile to the tinySA console where useful."""
    rbw_arg = "auto" if profile.rbw_khz is None else str(int(profile.rbw_khz))
    send_command(
        ser,
        f"rbw {rbw_arg}",
        delay_seconds=0.2,
        response_window_seconds=1.5,
        debug_log=debug_log,
    )

    if profile.sync_device_sweep:
        start_hz = int(round(profile.low_mhz * 1_000_000))
        stop_hz = int(round(profile.high_mhz * 1_000_000))
        display_points = min(max(int(profile.points), 101), 450)
        send_command(
            ser,
            f"sweep {start_hz} {stop_hz} {display_points}",
            delay_seconds=0.25,
            response_window_seconds=2.0,
            debug_log=debug_log,
        )


def read_scanraw_profile(ser, profile, progress_callback=None, cancel_check=None, debug_log=None):
    points = int(profile.points)
    start_hz = int(round(profile.low_mhz * 1_000_000))
    stop_hz = int(round(profile.high_mhz * 1_000_000))
    raw = send_binary_command(
        ser,
        f"scanraw {start_hz} {stop_hz} {points} 0",
        expected_payload_bytes=points * 3,
        max_seconds=max(20.0, min(180.0, points / 180.0)),
        progress_callback=progress_callback,
        cancel_check=cancel_check,
        debug_log=debug_log,
    )
    values = decode_scanraw_dbm(raw, points, ultra=True)
    if not values:
        raise RuntimeError("The tinySA returned no scanraw data.")
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

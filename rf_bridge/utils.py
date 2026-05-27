"""Small shared helpers for RF Bridge."""

import re
from datetime import datetime


def time_12h():
    return datetime.now().strftime("%I:%M:%S %p").lstrip("0")


def safe_name(text):
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_") or "gig"


def parse_numbers(output):
    nums = []

    for line in output.splitlines():
        try:
            nums.append(float(line.strip()))
        except ValueError:
            pass

    return nums


def clean_tinysa_version(output):
    """Return a compact tinySA version label from raw console output."""
    for line in str(output or "").replace("\r", "\n").splitlines():
        text = line.strip()
        lowered = text.lower()
        if not text or lowered in {"version", "ch>"} or lowered.endswith("ch>"):
            continue
        if "tinysa" in lowered or "hw version" in lowered:
            return text.replace("_", " ")

    return "tinySA"

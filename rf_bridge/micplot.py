"""Mic/frequency plot marker persistence and validation."""

import json

DEFAULT_MARKER_COLOR = "#00ff99"
MARKER_COLORS = [
    ("Green", "#00ff99"),
    ("Blue", "#33aaff"),
    ("Cyan", "#00e5ff"),
    ("Yellow", "#ffaa00"),
    ("Orange", "#ff7a00"),
    ("Red", "#ff3333"),
    ("Magenta", "#ff33cc"),
    ("Purple", "#cc66ff"),
    ("Violet", "#b388ff"),
    ("Lime", "#7cff00"),
    ("Teal", "#00c7a8"),
    ("Pink", "#ff8ad8"),
    ("White", "#eeeeee"),
    ("Gray", "#a0a0a0"),
]


def normalize_marker(marker):
    """Return a clean marker dict or raise ValueError."""
    name = str(marker.get("name", "")).strip()
    if not name:
        raise ValueError("Marker name is required.")

    try:
        frequency_mhz = float(marker.get("frequency_mhz"))
    except (TypeError, ValueError):
        raise ValueError(f"Marker '{name}' needs a valid MHz value.")

    if frequency_mhz <= 0:
        raise ValueError(f"Marker '{name}' frequency must be greater than 0 MHz.")

    color = str(marker.get("color", DEFAULT_MARKER_COLOR)).strip() or DEFAULT_MARKER_COLOR
    visible = bool(marker.get("visible", True))

    return {
        "name": name,
        "frequency_mhz": frequency_mhz,
        "color": color,
        "visible": visible,
    }


def load_markers(settings):
    raw = settings.get("mic_plot_markers", "[]")
    try:
        parsed = json.loads(str(raw))
    except (TypeError, ValueError):
        return []

    markers = []
    for marker in parsed if isinstance(parsed, list) else []:
        try:
            markers.append(normalize_marker(marker))
        except ValueError:
            continue
    return markers


def save_markers(settings, markers):
    cleaned = [normalize_marker(marker) for marker in markers]
    settings.set("mic_plot_markers", json.dumps(cleaned, indent=2))
    return cleaned

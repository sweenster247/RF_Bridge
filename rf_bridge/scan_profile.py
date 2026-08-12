"""Scan profile presets and tinySA acquisition settings."""

from __future__ import annotations

from dataclasses import dataclass
import math


ACQUISITION_COMPATIBILITY = "compatibility"
ACQUISITION_SCANRAW = "scanraw"


RBW_OPTIONS_KHZ = [
    ("Auto", None),
    ("600 kHz", 600),
    ("300 kHz", 300),
    ("100 kHz", 100),
    ("30 kHz", 30),
    ("10 kHz", 10),
    ("3 kHz", 3),
]


def clamp_points(value):
    try:
        points = int(value)
    except (TypeError, ValueError, OverflowError):
        points = 5500
    return max(101, min(points, 50000))


def normalize_rbw_khz(value):
    if value in (None, ""):
        return None
    allowed_values = {option_value for _label, option_value in RBW_OPTIONS_KHZ if option_value is not None}
    try:
        rbw_khz = int(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return rbw_khz if rbw_khz in allowed_values else None


SCAN_RANGE_PRESETS = [
    ("Broadcast UHF / TV 14-36", 470.000, 608.000),
    ("600 MHz Duplex Gap", 653.000, 663.000),
    ("Shure ULX-D G50", 470.000, 534.000),
    ("Shure ULX-D H50", 534.000, 598.000),
    ("Shure ULX-D J50A", 572.000, 616.000),
    ("Shure ULX-D J51", 572.000, 636.000),
    ("Shure ULX-D L50", 632.000, 696.000),
    ("Shure ULX-D L53", 632.000, 714.000),
    ("Shure Axient Digital G53", 470.000, 510.000),
    ("Shure Axient Digital G54", 479.000, 565.000),
    ("Shure Axient Digital G55/G56", 470.000, 636.000),
    ("Shure Axient Digital G57", 470.000, 608.000),
    ("Shure Axient Digital H54", 520.000, 636.000),
    ("Shure Axient Digital K54", 606.000, 663.000),
    ("Shure Axient Digital K55", 606.000, 694.000),
    ("Shure Axient Digital K56", 606.000, 714.000),
    ("Shure Axient Digital K58", 622.000, 698.000),
    ("Shure Axient Digital L60", 630.000, 698.000),
    ("Shure PSM 300 G20", 488.000, 512.000),
    ("Shure PSM 300 H20", 518.000, 542.000),
    ("Shure PSM 300 J13", 566.000, 590.000),
    ("Shure PSM 300 L18", 630.000, 654.000),
    ("Shure PSM 900 G6", 470.000, 506.000),
    ("Shure PSM 900 G7", 506.000, 542.000),
    ("Shure PSM 900 K1", 596.000, 632.000),
    ("Shure PSM 900 L6", 656.000, 692.000),
    ("Shure PSM 1000 G10", 470.000, 542.000),
    ("Shure PSM 1000 J8", 554.000, 626.000),
    ("Shure PSM 1000 L8", 626.000, 698.000),
    ("Custom Range", 470.000, 608.000),
]


@dataclass
class ScanProfile:
    label: str = "Broadcast UHF / TV 14-36"
    low_mhz: float = 470.0
    high_mhz: float = 608.0
    rbw_khz: int | None = None
    points: int = 5500
    acquisition_mode: str = ACQUISITION_SCANRAW
    sync_device_sweep: bool = False

    def __post_init__(self):
        self.label = str(self.label or "Custom Range")
        try:
            self.low_mhz = float(self.low_mhz)
            self.high_mhz = float(self.high_mhz)
        except (TypeError, ValueError, OverflowError):
            self.low_mhz, self.high_mhz = 470.0, 608.0
        if (
            not math.isfinite(self.low_mhz)
            or not math.isfinite(self.high_mhz)
            or self.high_mhz <= self.low_mhz
        ):
            self.low_mhz, self.high_mhz = 470.0, 608.0
        self.rbw_khz = normalize_rbw_khz(self.rbw_khz)
        self.points = clamp_points(self.points)
        if self.acquisition_mode not in {ACQUISITION_COMPATIBILITY, ACQUISITION_SCANRAW}:
            self.acquisition_mode = ACQUISITION_SCANRAW
        self.sync_device_sweep = bool(self.sync_device_sweep)

    def frequency_axis_mhz(self):
        if self.points <= 1:
            return [float(self.low_mhz)]
        step = (float(self.high_mhz) - float(self.low_mhz)) / (self.points - 1)
        return [
            float(self.low_mhz) + (index * step)
            for index in range(self.points)
        ]

    def summary(self):
        rbw = "Auto" if self.rbw_khz is None else f"{self.rbw_khz} kHz"
        mode = "scanraw" if self.acquisition_mode == ACQUISITION_SCANRAW else "compat"
        return (
            f"{self.label}: {self.low_mhz:.3f}-{self.high_mhz:.3f} MHz, "
            f"RBW {rbw}, {self.points} pts, {mode}"
        )

def estimate_points(low_mhz, high_mhz, rbw_khz):
    span_khz = max(1.0, abs(float(high_mhz) - float(low_mhz)) * 1000.0)
    if rbw_khz is None:
        target_step_khz = 25.0
    else:
        # Slightly oversample the selected RBW so adjacent bins overlap enough
        # for useful coordination exports without making wide scans absurd.
        target_step_khz = max(2.0, float(rbw_khz) / 2.0)
    return clamp_points(round(span_khz / target_step_khz) + 1)


def estimate_scan_seconds(points, rbw_khz=None):
    """Return a rough high-resolution tinySA scan duration estimate."""
    points = max(1, int(points))
    rbw_factor = 1.0
    if rbw_khz is not None:
        # Narrow RBW settings take longer; keep this intentionally rough until
        # measured device timings teach RF Bridge better values.
        rbw_factor = max(1.0, 30.0 / max(float(rbw_khz), 1.0))
    return max(1.0, (points / 900.0) * rbw_factor)


def recommended_refresh_seconds(scan_seconds):
    return max(0.5, round((float(scan_seconds) * 1.20) + 0.5, 1))


def profile_from_settings(settings):
    label = str(settings.get("scan_profile_label", "Broadcast UHF / TV 14-36"))
    low_mhz = settings.get_float("scan_profile_low_mhz", 470.0)
    high_mhz = settings.get_float("scan_profile_high_mhz", 608.0)
    rbw_value = settings.get("scan_profile_rbw_khz", "")
    try:
        rbw_khz = int(rbw_value) if str(rbw_value).strip() else None
    except (TypeError, ValueError):
        rbw_khz = None
    points = clamp_points(settings.get_float("scan_profile_points", 5500))
    acquisition_mode = str(settings.get("scan_profile_acquisition_mode", ACQUISITION_SCANRAW))
    if acquisition_mode not in {ACQUISITION_COMPATIBILITY, ACQUISITION_SCANRAW}:
        acquisition_mode = ACQUISITION_SCANRAW
    sync_device_sweep = settings.get_bool("scan_profile_sync_device_sweep", False)
    if high_mhz <= low_mhz:
        low_mhz, high_mhz = 470.0, 608.0
    return ScanProfile(
        label=label,
        low_mhz=float(low_mhz),
        high_mhz=float(high_mhz),
        rbw_khz=rbw_khz,
        points=points,
        acquisition_mode=acquisition_mode,
        sync_device_sweep=sync_device_sweep,
    )


def save_profile_to_settings(settings, profile):
    settings.set("scan_profile_label", profile.label)
    settings.set("scan_profile_low_mhz", float(profile.low_mhz))
    settings.set("scan_profile_high_mhz", float(profile.high_mhz))
    settings.set("scan_profile_rbw_khz", "" if profile.rbw_khz is None else int(profile.rbw_khz))
    settings.set("scan_profile_points", int(profile.points))
    settings.set("scan_profile_acquisition_mode", profile.acquisition_mode)
    settings.set("scan_profile_sync_device_sweep", bool(profile.sync_device_sweep))

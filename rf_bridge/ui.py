"""PySide6 / pyqtgraph RF Bridge UI."""

import bisect
from collections import deque
import heapq
import json
import math
import os
import random
import re
import time
import webbrowser

from .capture import load_capture_csv
from .micplot import MARKER_COLORS, DEFAULT_MARKER_COLOR, load_markers, save_markers
from .config import SCAN_INTERVAL_SECONDS, UI_UPDATE_SECONDS
from .export import save_wwb_csv
from .settings import AppSettings
from .tinysa import candidate_serial_ports, describe_port, find_tinysa_port
from .utils import time_12h
from .worker import ScanWorker
from .version import __version__


REFRESH_MODES = [0.5, 1, 2, 5, 10]
MAX_CONSECUTIVE_SCAN_MISMATCHES = 3
MAX_AUTO_TRACE_OVERLAYS = 6
FREQUENCY_DISPLAY_STEP_MHZ = 0.005
DEVICE_UNAVAILABLE_MARKERS = (
    "device not configured",
    "no such file",
    "input/output error",
    "i/o error",
    "write failed",
    "read failed",
    "could not open port",
    "could not reconnect",
    "stopped responding",
)
PEAK_MODES = [
    ("OFF", None),
    ("LATCH", "latch"),
    ("1 min", 60),
    ("5 min", 300),
    ("15 min", 900),
]

THEMES = {
    "Dark": {
        "window_bg": "#111111",
        "panel_bg": "#181818",
        "side_bg": "#141414",
        "plot_bg": "#181818",
        "text": "#eeeeee",
        "muted_text": "#dddddd",
        "border": "#555555",
        "button_bg": "#222222",
        "button_hover": "#333333",
        "button_pressed": "#444444",
        "button_disabled_bg": "#191919",
        "button_disabled_text": "#777777",
        "log_bg": "#0f0f0f",
        "hover_bg": "#202020",
        "disconnected": "#aa3333",
        "connected": "#33cc77",
        "axis": "#888888",
        "axis_text": "#dddddd",
        "marker": "#666666",
    },
    "Light": {
        "window_bg": "#f5f5f5",
        "panel_bg": "#ffffff",
        "side_bg": "#fafafa",
        "plot_bg": "#ffffff",
        "text": "#202020",
        "muted_text": "#303030",
        "border": "#c8c8c8",
        "button_bg": "#f0f0f0",
        "button_hover": "#e4e4e4",
        "button_pressed": "#d6d6d6",
        "button_disabled_bg": "#eeeeee",
        "button_disabled_text": "#999999",
        "log_bg": "#ffffff",
        "hover_bg": "#f7f7f7",
        "disconnected": "#b00020",
        "connected": "#087f3f",
        "axis": "#555555",
        "axis_text": "#202020",
        "marker": "#909090",
    },
}

APPEARANCE_OPTIONS = ["System", "Dark", "Light"]
DEMO_PORT = "__rf_bridge_demo__"
DEMO_RANGE_PRESETS = [
    ("Broadcast UHF / TV 14–36", 470.000, 608.000),
    ("Shure G50-style UHF", 470.000, 534.000),
    ("Shure H50-style UHF", 534.000, 598.000),
    ("Shure J50A-style UHF", 572.000, 616.000),
    ("Legacy 470–560 MHz demo", 470.000, 560.000),
]
DEMO_CONNECT_HOLD_MS = 2000

# Fixed RF display range. Keep the graph from re-scaling when the tinySA
# connects, when live data arrives, or when guide/marker items are refreshed.
RF_Y_MIN = -110
RF_Y_MAX = -10
RF_Y_RANGE = RF_Y_MAX - RF_Y_MIN
MIC_MARKER_HIT_RADIUS_MHZ = 0.25
MIC_MARKER_LABEL_LANES = [-18, -30, -42, -54, -66]
MIC_MARKER_LABEL_MIN_GAP_MHZ = 8.0
MIC_MARKER_LABEL_GAP_RATIO = 0.075
MIC_MARKER_LABEL_PIXEL_PADDING = 28


class UiBridgeFactory:
    """Create a QObject signal bridge after PySide6 is available.

    Worker signals are emitted from the scan thread. Connecting them directly
    to plain Python methods can execute UI updates in the worker thread. This
    bridge lives in the GUI thread and re-emits those events safely.
    """

    @staticmethod
    def create():
        from PySide6.QtCore import QObject, Signal

        class UiBridge(QObject):
            connected = Signal(str, str, list)
            scan_ready = Signal(list)
            disconnected = Signal()
            reconnecting = Signal(str)
            error = Signal(str)
            log = Signal(str)

        return UiBridge()


class BoundedFrequencyViewBoxFactory:
    """Create a pyqtgraph ViewBox that keeps horizontal navigation in range."""

    @staticmethod
    def create(pg, qt, reset_callback, context_callback):
        class BoundedFrequencyViewBox(pg.ViewBox):
            def __init__(self):
                super().__init__()
                self.frequency_bounds = None

            def set_frequency_bounds(self, bounds):
                self.frequency_bounds = bounds
                if bounds:
                    low, high = bounds
                    span = max(high - low, 0.001)
                    # Allow useful wheel zoom, but prevent zooming so far in
                    # that the trace becomes disorienting or numerically tiny.
                    self.setLimits(
                        xMin=low,
                        xMax=high,
                        minXRange=max(0.25, span / 500.0),
                        maxXRange=span,
                    )
                self.clamp_x_range()

            def _wheel_delta(self, event):
                try:
                    pixel_delta = event.pixelDelta()
                    if not pixel_delta.isNull():
                        return pixel_delta.x(), pixel_delta.y(), 80.0
                except Exception:
                    pass

                try:
                    angle_delta = event.angleDelta()
                    return angle_delta.x(), angle_delta.y(), 120.0
                except Exception:
                    return 0.0, 0.0, 120.0

            def _clamped_range(self, requested_low, requested_high):
                if not self.frequency_bounds:
                    return requested_low, requested_high

                low, high = self.frequency_bounds
                span = high - low
                if span <= 0:
                    return low, high

                width = requested_high - requested_low
                width = min(max(width, max(0.25, span / 500.0)), span)

                if requested_low < low:
                    requested_low = low
                    requested_high = low + width
                elif requested_high > high:
                    requested_high = high
                    requested_low = high - width

                return requested_low, requested_high

            def clamp_x_range(self):
                if not self.frequency_bounds:
                    return

                current_low, current_high = self.viewRange()[0]
                target = self._clamped_range(current_low, current_high)
                if target != (current_low, current_high):
                    self.setXRange(target[0], target[1], padding=0)

            def wheelEvent(self, event, axis=None):
                if not self.frequency_bounds:
                    super().wheelEvent(event, axis=axis)
                    return

                delta_x, delta_y, unit = self._wheel_delta(event)
                if delta_x == 0 and delta_y == 0:
                    event.ignore()
                    return

                current_low, current_high = self.viewRange()[0]
                width = current_high - current_low

                # Horizontal wheel / trackpad gestures pan across the selected
                # RF range without leaving the scan boundaries. Vertical wheel
                # gestures zoom the frequency axis around the cursor position.
                if abs(delta_x) > abs(delta_y):
                    steps = delta_x / unit
                    shift_mhz = steps * width * 0.12
                    target_low, target_high = self._clamped_range(
                        current_low + shift_mhz,
                        current_high + shift_mhz,
                    )
                    self.setXRange(target_low, target_high, padding=0)
                    event.accept()
                    return

                try:
                    cursor_x = self.mapSceneToView(event.scenePos()).x()
                except Exception:
                    cursor_x = (current_low + current_high) / 2.0

                zoom_steps = delta_y / unit
                zoom_factor = 0.85 ** zoom_steps if zoom_steps else 1.0
                new_width = width * zoom_factor
                cursor_ratio = 0.5 if width <= 0 else (cursor_x - current_low) / width
                cursor_ratio = min(max(cursor_ratio, 0.0), 1.0)
                target_low = cursor_x - new_width * cursor_ratio
                target_high = target_low + new_width
                target_low, target_high = self._clamped_range(target_low, target_high)
                self.setXRange(target_low, target_high, padding=0)
                event.accept()

            def mouseDragEvent(self, event, axis=None):
                super().mouseDragEvent(event, axis=axis)
                self.clamp_x_range()

            def mouseDoubleClickEvent(self, event):
                if event.button() == qt.LeftButton:
                    event.accept()
                    reset_callback()
                    return
                super().mouseDoubleClickEvent(event)

            def raiseContextMenu(self, event):
                event.accept()
                context_callback(event)

        return BoundedFrequencyViewBox()


class AutoDetectWorkerFactory:
    """Create a worker that probes tinySA ports away from the GUI thread."""

    @staticmethod
    def create():
        from PySide6.QtCore import QObject, Signal, Slot

        class AutoDetectWorker(QObject):
            detected = Signal(str, str, list)
            skipped = Signal(str)
            finished = Signal()

            @Slot()
            def start(self):
                try:
                    port, header, scanned = find_tinysa_port()
                    self.detected.emit(port, header, scanned)
                except Exception as exc:
                    self.skipped.emit(str(exc))
                finally:
                    self.finished.emit()

        return AutoDetectWorker()


def format_seconds(seconds):
    if float(seconds).is_integer():
        return str(int(seconds))
    return str(seconds)


def snap_display_frequency(freq_mhz):
    return round(freq_mhz / FREQUENCY_DISPLAY_STEP_MHZ) * FREQUENCY_DISPLAY_STEP_MHZ


def compact_capture_label(name):
    """Create a short overlay label from RF Bridge capture filenames."""
    stem = os.path.splitext(os.path.basename(name or "Capture"))[0]
    match = re.match(
        r"^(\d{4}-\d{2}-\d{2})_(Morning|Afternoon|Evening|Overnight|morning|afternoon|evening|overnight)_(\d{2})-(\d{2})(AM|PM)?_(.+)$",
        stem,
    )
    if match:
        date_part, daypart, hour, minute, ampm, remainder = match.groups()
        remainder_parts = [part for part in remainder.split("_") if part]
        device = remainder_parts[-1] if remainder_parts else ""
        session = " ".join(remainder_parts[:-1]).strip()
        label = f"{daypart.title()} {hour}:{minute}{ampm or ''}"
        if session:
            label += f" · {session[:18]}"
        if device:
            label += f" · {device}"
        return label

    legacy_match = re.match(r"^(\d{4}-\d{2}-\d{2})_(\d{2})-(\d{2})(?:-\d{2})?_(.+)$", stem)
    if legacy_match:
        _date_part, hour, minute, remainder = legacy_match.groups()
        return f"{hour}:{minute} · {remainder[:26]}"

    return stem[:42] + ("…" if len(stem) > 42 else "")


def capture_overlay_daypart(name):
    """Return the capture daypart encoded in RF Bridge filenames."""
    stem = os.path.splitext(os.path.basename(name or ""))[0]
    match = re.match(
        r"^\d{4}-\d{2}-\d{2}_(Morning|Afternoon|Evening|Overnight|morning|afternoon|evening|overnight)_",
        stem,
    )
    if match:
        return match.group(1).title()
    return "Other"


class RFBridgeWindow:
    def __init__(self, output_dir, gig_slug, ui_update_seconds=UI_UPDATE_SECONDS, selected_port=None, debug_serial=False):
        from PySide6.QtCore import Qt, QThread, Signal, QMetaObject, Q_ARG, QTimer, QSize
        from PySide6.QtGui import QAction, QIcon, QPixmap
        from PySide6.QtWidgets import (
            QApplication,
            QCheckBox,
            QComboBox,
            QFrame,
            QGridLayout,
            QHBoxLayout,
            QLabel,
            QMainWindow,
            QMenu,
            QMessageBox,
            QPushButton,
            QSizePolicy,
            QTextEdit,
            QVBoxLayout,
            QWidget,
        )
        import pyqtgraph as pg

        self.Qt = Qt
        self.QThread = QThread
        self.Signal = Signal
        self.QMetaObject = QMetaObject
        self.Q_ARG = Q_ARG
        self.QMessageBox = QMessageBox
        self.QMenu = QMenu
        self.QTimer = QTimer
        self.QAction = QAction
        self.pg = pg

        self.output_dir = output_dir
        self.gig_slug = gig_slug
        self.selected_port = selected_port
        self.device_name = "tinySA"
        self.debug_serial = debug_serial
        self.freqs_mhz = []
        self.latest_dbm = []
        self.display_dbm = []
        self.last_save_time = 0
        self.last_cursor_index = None
        self.peak_mode_index = 0
        self.peak_enabled = False
        self.peak_hold = None
        self.peak_history = deque()
        self.top_markers = []
        self.mic_markers = []
        self.mic_marker_items = []
        self.mic_marker_label_items = []
        self.frozen = False
        self.loaded_capture = None
        self.capture_mode = False
        self.capture_overlays = []
        self.capture_overlay_items = []
        self.capture_overlay_actions = []
        self.overlay_checkbox_widgets = []
        self.overlay_checkbox_indexes = []
        self.overlay_color_index = 0
        self.last_auto_trace_time = 0
        self.scan_error_count = 0
        self.scan_mismatch_count = 0
        self.auto_connect_in_progress = False
        self.force_disconnected_actions = False
        self.pending_disconnect_status = None
        self.shutting_down = False
        self.shutdown_started = False
        self.live_freqs_mhz = []
        self.connected = False
        self.worker_thread = None
        self.worker = None
        self.auto_detect_thread = None
        self.auto_detect_worker = None
        self.port_selection_touched = False
        self.suppress_plot_click_until = 0.0
        self.demo_timer = None
        self.demo_phase = 0.0
        self.demo_mode = False
        self.demo_connect_pending = False
        self.demo_low_mhz = 470.0
        self.demo_high_mhz = 608.0
        self.port_map = {}
        self.settings = AppSettings()
        self.auto_trace_enabled = self.settings.get_bool("auto_trace_enabled", False)
        self.auto_trace_minutes = max(1.0, self.settings.get_float("auto_trace_minutes", 10.0))
        self.filename_time_format = self.settings.get_filename_time_format()
        self.appearance = self.settings.get_appearance()
        self.theme_name = self.resolve_theme_name(self.appearance)
        self.theme = THEMES[self.theme_name]
        self.ui_bridge = UiBridgeFactory.create()
        self.ui_bridge.connected.connect(self.on_connected)
        self.ui_bridge.scan_ready.connect(self.on_scan_ready)
        self.ui_bridge.error.connect(self.on_worker_error)
        self.ui_bridge.reconnecting.connect(self.on_worker_reconnecting)
        self.ui_bridge.log.connect(self.log)
        self.ui_bridge.disconnected.connect(self.on_disconnected)

        saved_refresh = self.settings.get_float("refresh_seconds", ui_update_seconds)
        self.refresh_index = min(
            range(len(REFRESH_MODES)),
            key=lambda index: abs(REFRESH_MODES[index] - saved_refresh),
        )
        self.refresh_seconds = float(saved_refresh)
        self.selected_port = selected_port or self.settings.get("last_port", None)

        self.app = QApplication.instance() or QApplication([])
        # Re-enable normal desktop-app behavior now that a real main window
        # exists. Startup dialogs temporarily disable this in app.py.
        self.app.setQuitOnLastWindowClosed(True)
        self.window = QMainWindow()
        self.window.closeEvent = self.handle_close_event
        self.app.aboutToQuit.connect(self.shutdown)
        self.window.setWindowTitle("RF Bridge")
        self.window.resize(1640, 940)
        self.window.setMinimumSize(1280, 760)

        saved_geometry = self.settings.get_bytes("window_geometry")
        if saved_geometry:
            self.window.restoreGeometry(saved_geometry)
            if self.window.width() < 1280 or self.window.height() < 760:
                self.window.resize(max(self.window.width(), 1280), max(self.window.height(), 760))

        root = QWidget()
        shell_layout = QHBoxLayout(root)
        shell_layout.setContentsMargins(8, 8, 8, 8)
        shell_layout.setSpacing(8)

        sidebar_panel = QFrame()
        sidebar_panel.setObjectName("navigationPanel")
        sidebar_panel.setFixedWidth(285)
        sidebar_layout = QVBoxLayout(sidebar_panel)
        sidebar_layout.setContentsMargins(18, 18, 18, 18)
        sidebar_layout.setSpacing(12)

        brand_box = QVBoxLayout()
        brand_box.setContentsMargins(0, 2, 0, 4)
        brand_box.setSpacing(6)

        self.sidebar_logo = QLabel()
        self.sidebar_logo.setObjectName("sidebarLogo")
        self.sidebar_logo.setFixedSize(145, 145)
        logo_path = self.asset_path("sidebar-logo-dark.png")
        if os.path.exists(logo_path):
            logo_pixmap = QPixmap(logo_path)
            if not logo_pixmap.isNull():
                self.sidebar_logo.setPixmap(
                    logo_pixmap.scaled(
                        QSize(145, 145),
                        self.Qt.KeepAspectRatio,
                        self.Qt.SmoothTransformation,
                    )
                )
        self.sidebar_logo.setAlignment(self.Qt.AlignCenter)

        self.sidebar_title = QLabel("RF Bridge")
        self.sidebar_title.setObjectName("sidebarTitle")
        self.sidebar_title.setAlignment(self.Qt.AlignCenter)
        self.sidebar_subtitle = QLabel("RF Spectrum Analyzer")
        self.sidebar_subtitle.setObjectName("sidebarSubtitle")
        self.sidebar_subtitle.setAlignment(self.Qt.AlignCenter)
        self.sidebar_subtitle.setWordWrap(False)

        brand_box.addWidget(self.sidebar_logo, alignment=self.Qt.AlignCenter)
        brand_box.addWidget(self.sidebar_title)
        brand_box.addWidget(self.sidebar_subtitle)
        sidebar_layout.addLayout(brand_box)
        sidebar_layout.addSpacing(16)

        self.rf_scan_button = QPushButton("RF Scan")
        self.mic_plot_nav_button = QPushButton("Markers / Mic Plot")
        self.capture_nav_button = QPushButton("Capture Overlays")
        self.preferences_nav_button = QPushButton("Preferences")
        self.about_nav_button = QPushButton("About / Help")

        for button in (
            self.rf_scan_button,
            self.mic_plot_nav_button,
            self.capture_nav_button,
            self.preferences_nav_button,
            self.about_nav_button,
        ):
            button.setObjectName("sidebarButton")
            button.setMinimumHeight(42)
            button.setFlat(True)
            sidebar_layout.addWidget(button)

        self.rf_scan_button.setEnabled(False)
        sidebar_layout.addStretch(1)
        self.sidebar_connection_label = QLabel("Disconnected")
        self.sidebar_connection_label.setObjectName("sidebarConnectionLabel")
        self.sidebar_device_label = QLabel("Device: —")
        self.sidebar_device_label.setObjectName("sidebarDeviceLabel")
        self.sidebar_device_label.setWordWrap(True)
        sidebar_layout.addWidget(self.sidebar_connection_label)
        sidebar_layout.addWidget(self.sidebar_device_label)

        root_layout = QVBoxLayout()
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(8)

        shell_layout.addWidget(sidebar_panel)
        shell_layout.addLayout(root_layout, stretch=1)

        connection_panel = QFrame()
        connection_panel.setObjectName("connectionPanel")
        connection_layout = QGridLayout(connection_panel)
        connection_layout.setContentsMargins(10, 8, 10, 8)
        connection_layout.setHorizontalSpacing(6)
        connection_layout.setVerticalSpacing(4)

        self.status_dot = QLabel("●")
        self.status_dot.setObjectName("statusDot")
        self.status_dot.setFixedWidth(18)
        self.connection_status = QLabel("Disconnected")
        self.connection_status.setObjectName("connectionStatus")
        self.connection_status.setMinimumWidth(0)
        self.connection_status.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.port_combo = QComboBox()
        self.refresh_ports_button = QPushButton("Refresh")
        self.connect_button = QPushButton("Connect")
        self.disconnect_button = QPushButton("Disconnect")
        self.disconnect_button.setObjectName("secondaryButton")
        self.disconnect_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.disconnect_button.setEnabled(False)
        self.disconnect_button.setVisible(False)
        self.device_info_label = QLabel("Device: —\nRange: —")
        self.device_info_label.setObjectName("deviceInfoLabel")
        self.device_info_label.setMinimumWidth(0)
        self.device_info_label.setFixedHeight(42)
        self.device_info_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        self.device_notice_label = QLabel("")
        self.device_notice_label.setObjectName("deviceNoticeLabel")
        self.device_notice_label.setWordWrap(True)
        self.device_notice_label.setMinimumWidth(0)
        self.device_notice_label.setFixedHeight(44)
        self.device_notice_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        self.device_notice_label.setVisible(False)

        self.port_combo.setMinimumWidth(205)
        self.port_combo.setMaximumWidth(310)
        self.port_combo.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        self.port_combo.view().setTextElideMode(self.Qt.ElideMiddle)
        for _btn in (self.refresh_ports_button, self.connect_button, self.disconnect_button):
            _btn.setMinimumHeight(24)
            _btn.setMaximumHeight(28)
        self.disconnect_button.setEnabled(False)

        connection_layout.addWidget(self.status_dot, 0, 0)
        connection_layout.addWidget(self.connection_status, 0, 1, 1, 2)
        connection_layout.addWidget(self.disconnect_button, 0, 3, 1, 1)
        connection_layout.addWidget(self.port_combo, 1, 0, 1, 4)
        connection_layout.addWidget(self.connect_button, 2, 0, 1, 2)
        connection_layout.addWidget(self.refresh_ports_button, 2, 2, 1, 2)
        connection_layout.addWidget(self.device_info_label, 3, 0, 1, 4)
        connection_layout.addWidget(self.device_notice_label, 4, 0, 1, 4)
        connection_layout.setColumnStretch(1, 1)
        connection_panel.setFixedWidth(360)
        connection_panel.setFixedHeight(195)

        self.overlay_panel = QFrame()
        self.overlay_panel.setObjectName("overlayPanel")
        self.overlay_panel.setFixedHeight(195)
        overlay_layout = QVBoxLayout(self.overlay_panel)
        overlay_layout.setContentsMargins(14, 10, 14, 10)
        overlay_layout.setSpacing(8)

        overlay_header = QHBoxLayout()
        self.overlay_icon = QLabel("▱")
        self.overlay_icon.setObjectName("overlayHeaderIcon")
        self.overlay_title = QLabel("CAPTURE OVERLAYS")
        self.overlay_title.setObjectName("overlayTitle")
        self.overlay_subtitle = QLabel("Load previously saved scans to overlay on the live RF data.")
        self.overlay_subtitle.setObjectName("overlaySubtitle")
        overlay_title_stack = QVBoxLayout()
        overlay_title_stack.setContentsMargins(0, 0, 0, 0)
        overlay_title_stack.setSpacing(1)
        overlay_title_stack.addWidget(self.overlay_title)
        overlay_title_stack.addWidget(self.overlay_subtitle)
        self.open_overlay_button = QPushButton("Open Overlay(s)…")
        self.clear_overlay_button = QPushButton("Clear All")
        overlay_header.addWidget(self.overlay_icon)
        overlay_header.addLayout(overlay_title_stack, stretch=1)
        overlay_header.addWidget(self.open_overlay_button)
        overlay_header.addWidget(self.clear_overlay_button)

        self.overlay_content_frame = QFrame()
        self.overlay_content_frame.setObjectName("overlayContentFrame")
        overlay_content_layout = QVBoxLayout(self.overlay_content_frame)
        overlay_content_layout.setContentsMargins(12, 8, 12, 8)
        overlay_content_layout.setSpacing(4)
        self.overlay_controls_row = QGridLayout()
        self.overlay_controls_row.setHorizontalSpacing(10)
        self.overlay_controls_row.setVerticalSpacing(6)
        self.overlay_empty_label = QLabel("No overlays loaded")
        self.overlay_empty_label.setObjectName("overlayEmptyLabel")
        self.overlay_empty_label.setAlignment(self.Qt.AlignCenter)
        self.overlay_empty_hint = QLabel("Click “Open Overlay(s)…” to load one or more capture files (CSV).")
        self.overlay_empty_hint.setObjectName("overlayEmptyHint")
        self.overlay_empty_hint.setAlignment(self.Qt.AlignCenter)
        self.overlay_controls_row.addWidget(self.overlay_empty_label, 0, 0, 1, 2)
        overlay_content_layout.addStretch(1)
        overlay_content_layout.addLayout(self.overlay_controls_row)
        overlay_content_layout.addWidget(self.overlay_empty_hint)
        overlay_content_layout.addStretch(1)

        overlay_layout.addLayout(overlay_header)
        overlay_layout.addWidget(self.overlay_content_frame, stretch=1)

        top_layout = QHBoxLayout()
        top_layout.setSpacing(10)
        top_layout.addWidget(self.overlay_panel, stretch=1)
        top_layout.addWidget(connection_panel, stretch=0)

        content_layout = QHBoxLayout()
        content_layout.setSpacing(8)

        pg.setConfigOptions(antialias=True)
        self.frequency_view_box = BoundedFrequencyViewBoxFactory.create(
            pg,
            self.Qt,
            self.reset_frequency_view,
            self.show_plot_context_menu,
        )
        self.plot = pg.PlotWidget(viewBox=self.frequency_view_box)
        self.plot.setBackground(self.theme["plot_bg"])
        self.plot.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.plot.showGrid(x=True, y=True, alpha=0.25)
        self.plot.setLabel("bottom", "Frequency", units="MHz")
        self.plot.setLabel("left", "dBm")
        self.plot.setTitle(f"RF Bridge - {self.gig_slug}", color=self.theme["text"], size="16pt")
        self.plot.getPlotItem().setMenuEnabled(False)
        self.lock_plot_axes()

        axis_pen = pg.mkPen(self.theme["axis"])
        self.plot.getAxis("bottom").setPen(axis_pen)
        self.plot.getAxis("left").setPen(axis_pen)
        self.plot.getAxis("bottom").setTextPen(self.theme["axis_text"])
        self.plot.getAxis("left").setTextPen(self.theme["axis_text"])
        self.plot.getAxis("left").setTickSpacing(major=10, minor=5)

        self.live_curve = self.plot.plot([], [], pen=pg.mkPen("#00ff99", width=2), name="Live")
        self.peak_curve = self.plot.plot([], [], pen=pg.mkPen("#ff3333", width=1.5), name="Peak Hold")
        self.threshold_85 = pg.InfiniteLine(pos=-85, angle=0, pen=pg.mkPen("#ffaa00", width=1, style=self.Qt.DashLine))
        self.threshold_60 = pg.InfiniteLine(pos=-60, angle=0, pen=pg.mkPen("#ff00aa", width=1, style=self.Qt.DashLine))
        self.plot.addItem(self.threshold_85, ignoreBounds=True)
        self.plot.addItem(self.threshold_60, ignoreBounds=True)
        self.cursor_line = pg.InfiniteLine(pos=0, angle=90, pen=pg.mkPen("#00ff99", width=1))
        self.cursor_line.setVisible(False)
        self.plot.addItem(self.cursor_line, ignoreBounds=True)
        self.low_freq_label = pg.TextItem("", color=self.theme["axis_text"], anchor=(0, 1))
        self.high_freq_label = pg.TextItem("", color=self.theme["axis_text"], anchor=(1, 1))
        for label in (self.low_freq_label, self.high_freq_label):
            label.setZValue(30)
            label.setVisible(False)
            self.plot.addItem(label, ignoreBounds=True)

        side_panel = QFrame()
        side_panel.setObjectName("sidePanel")
        # Give the RF summary / Top 8 readout a little more horizontal room.
        # This prevents clipping on macOS when labels, DPI scaling, or font
        # rendering make the right sidebar slightly tighter than expected.
        side_panel.setFixedWidth(360)
        side_layout = QVBoxLayout(side_panel)
        side_layout.setContentsMargins(12, 12, 12, 12)
        side_layout.setSpacing(10)

        self.summary_label = QLabel("RF SUMMARY\n──────────────────────\n\nConnect to tinySA to begin.")
        self.summary_label.setObjectName("summaryLabel")
        self.summary_label.setAlignment(self.Qt.AlignTop | self.Qt.AlignLeft)
        self.summary_label.setTextInteractionFlags(self.Qt.TextSelectableByMouse)
        self.hover_label = QLabel("Hover graph for readout.")
        self.hover_label.setObjectName("hoverLabel")
        self.hover_label.setAlignment(self.Qt.AlignTop | self.Qt.AlignLeft)
        self.hover_label.setTextInteractionFlags(self.Qt.TextSelectableByMouse)
        # Keep the hover readout from asking Qt's layout system for more height
        # as the cursor moves. Without this, vertical mouse movement over the
        # graph can make the main window grow unexpectedly on macOS.
        self.hover_label.setMinimumHeight(72)
        self.hover_label.setMaximumHeight(84)

        self.peak_button = QPushButton("  Peak OFF")
        self.peak_button.setToolTip("Cycle peak hold mode. Right-click for all peak options.")
        self.peak_button.setContextMenuPolicy(self.Qt.CustomContextMenu)
        self.reset_button = QPushButton("  Reset")
        self.reset_button.setToolTip("Clear peak hold data")
        self.refresh_button = QPushButton(f"  {format_seconds(self.refresh_seconds)}s")
        self.refresh_button.setToolTip("Cycle scan refresh interval. Right-click for all refresh options.")
        self.refresh_button.setContextMenuPolicy(self.Qt.CustomContextMenu)
        self.freeze_button = QPushButton("  Freeze")
        self.freeze_button.setToolTip("Freeze or resume the live trace")
        self.return_live_button = QPushButton("  Return to Live")
        self.return_live_button.setToolTip("Return the graph to the live trace")
        self.return_live_button.setEnabled(False)

        control_icons = (
            (self.peak_button, "icons/icon-peak.svg"),
            (self.reset_button, "icons/icon-reset.svg"),
            (self.refresh_button, "icons/icon-refresh.svg"),
            (self.freeze_button, "icons/icon-freeze.svg"),
            (self.return_live_button, "icons/icon-play.svg"),
        )
        for button, icon_name in control_icons:
            button.setMinimumHeight(34)
            button.setIcon(QIcon(self.asset_path(icon_name)))
            button.setIconSize(QSize(22, 22))

        peak_row = QHBoxLayout()
        peak_row.setSpacing(8)
        peak_row.addWidget(self.peak_button)
        peak_row.addWidget(self.reset_button)

        live_row = QHBoxLayout()
        live_row.setSpacing(8)
        live_row.addWidget(self.refresh_button)
        live_row.addWidget(self.freeze_button)

        side_layout.addWidget(self.summary_label, stretch=1)
        side_layout.addWidget(self.hover_label)
        side_layout.addLayout(peak_row)
        side_layout.addLayout(live_row)
        side_layout.addWidget(self.return_live_button)

        content_layout.addWidget(self.plot, stretch=1)
        content_layout.addWidget(side_panel)

        self.log_box = QTextEdit()
        self.log_box.setObjectName("logBox")
        self.log_box.setReadOnly(True)
        self.log_box.setFixedHeight(96)
        self.log_box.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        self.status_label = QLabel("")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setFixedHeight(38)
        self.status_label.setMinimumWidth(0)
        self.status_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        self.status_label.setTextInteractionFlags(self.Qt.TextSelectableByMouse)

        root_layout.addLayout(top_layout)
        root_layout.addLayout(content_layout, stretch=2)
        root_layout.addWidget(self.log_box)
        root_layout.addWidget(self.status_label)
        self.window.setCentralWidget(root)

        self.create_menus()
        self.apply_theme()

        self.refresh_ports_button.clicked.connect(self.populate_ports)
        self.port_combo.activated.connect(self.mark_port_selection_touched)
        self.connect_button.clicked.connect(self.connect_device)
        self.disconnect_button.clicked.connect(self.disconnect_device)
        self.peak_button.clicked.connect(self.toggle_peak)
        self.peak_button.customContextMenuRequested.connect(self.show_peak_menu)
        self.reset_button.clicked.connect(self.reset_peaks)
        self.refresh_button.clicked.connect(self.toggle_refresh)
        self.refresh_button.customContextMenuRequested.connect(self.show_refresh_menu)
        self.freeze_button.clicked.connect(self.toggle_freeze)
        self.return_live_button.clicked.connect(self.return_to_live)
        self.open_overlay_button.clicked.connect(self.open_capture_overlays)
        self.clear_overlay_button.clicked.connect(self.clear_capture_overlays)
        self.mic_plot_nav_button.clicked.connect(self.open_mic_plot)
        self.capture_nav_button.clicked.connect(self.open_capture_overlays)
        self.preferences_nav_button.clicked.connect(self.open_preferences)
        self.about_nav_button.clicked.connect(self.open_about)
        self.plot.scene().sigMouseMoved.connect(self.on_mouse_move)
        self.plot.scene().sigMouseClicked.connect(self.on_plot_mouse_click)
        self.plot.getViewBox().sigRangeChanged.connect(self.update_mic_marker_label_view_positions)
        self.window.destroyed.connect(self.shutdown)

        self.populate_ports()
        self.update_connection_state(False)
        self.update_status()
        self.mic_markers = load_markers(self.settings)
        self.render_mic_markers()
        self.log(f"RF Bridge v{__version__} ready")

        if selected_port:
            # Defer explicit manual-port connection until after the window is
            # shown and the Qt event loop is running.
            self.QTimer.singleShot(900, self.connect_device)
        else:
            self.log("Demo Mode is ready. Looking for tinySA in the background.")
            self.QTimer.singleShot(900, self.start_auto_detect)

    def resolve_theme_name(self, appearance):
        if appearance == "Light":
            return "Light"
        if appearance == "System":
            try:
                scheme = self.app.styleHints().colorScheme()
                if scheme == self.Qt.ColorScheme.Light:
                    return "Light"
            except Exception:
                pass
        return "Dark"

    def asset_path(self, filename):
        # Works from source and from PyInstaller app bundles where assets are
        # copied into the runtime directory.
        candidates = [
            os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", filename),
            os.path.join(os.path.dirname(__file__), "..", "assets", filename),
        ]
        bundle_root = getattr(__import__("sys"), "_MEIPASS", None)
        if bundle_root:
            candidates.insert(0, os.path.join(bundle_root, "assets", filename))
        for candidate in candidates:
            candidate = os.path.abspath(candidate)
            if os.path.exists(candidate):
                return candidate
        return os.path.abspath(candidates[-1])

    def stylesheet(self):
        t = self.theme
        return f"""
        QMainWindow, QWidget {{ background: {t['window_bg']}; color: {t['text']}; font-family: Arial, Helvetica; }}
        QMenuBar, QMenu {{ background: {t['panel_bg']}; color: {t['text']}; border: 1px solid {t['border']}; }}
        QMenuBar::item:selected, QMenu::item:selected {{ background: {t['button_hover']}; }}
        QFrame#connectionPanel, QFrame#overlayPanel {{ background: {t['panel_bg']}; border: 1px solid {t['border']}; border-radius: 10px; }}
        QFrame#overlayContentFrame {{ background: {t['window_bg']}; border: 1px dashed {t['border']}; border-radius: 8px; }}
        QFrame#navigationPanel {{ background: {t['side_bg']}; border: 1px solid {t['border']}; border-radius: 8px; }}
        QFrame#sidePanel {{ background: {t['side_bg']}; border-left: 1px solid {t['border']}; }}
        QLabel#summaryLabel, QLabel#hoverLabel {{ color: {t['text']}; font-family: Menlo, Monaco, Consolas, monospace; font-size: 13px; }}
        QLabel#hoverLabel {{ background: {t['hover_bg']}; border: 1px solid {t['border']}; border-radius: 6px; padding: 8px; }}
        QLabel#statusLabel {{ background: {t['panel_bg']}; border: 1px solid {t['border']}; border-radius: 6px; color: {t['text']}; font-family: Menlo, Monaco, Consolas, monospace; font-size: 12px; padding-left: 14px; }}
        QLabel#statusDot {{ color: {t['disconnected']}; font-size: 22px; background: transparent; }}
        QLabel#connectionStatus {{ font-weight: bold; background: {t['hover_bg']}; border: 1px solid {t['border']}; border-radius: 12px; padding: 3px 10px; font-size: 14px; }}
        QLabel#deviceInfoLabel {{ color: {t['muted_text']}; background: transparent; font-size: 12px; padding-top: 2px; }}
        QLabel#deviceNoticeLabel {{ color: {t['disconnected']}; background: transparent; font-size: 12px; padding-top: 2px; }}
        QLabel#overlayHeaderIcon {{ color: {t['text']}; font-size: 26px; font-weight: bold; padding-right: 4px; background: transparent; }}
        QLabel#overlayTitle {{ font-weight: bold; font-family: Menlo, Monaco, Consolas, monospace; font-size: 15px; background: transparent; }}
        QLabel#overlaySubtitle {{ color: {t['muted_text']}; font-size: 12px; background: transparent; }}
        QLabel#overlayEmptyLabel {{ color: {t['text']}; font-size: 16px; font-weight: bold; background: transparent; padding: 2px; }}
        QLabel#overlayEmptyHint {{ color: {t['muted_text']}; font-size: 12px; background: transparent; padding: 2px; }}
        QLabel#sidebarLogo {{ background: transparent; border: 0px; }}
        QLabel#sidebarTitle {{ font-weight: bold; color: {t['text']}; font-size: 24px; background: transparent; }}
        QLabel#sidebarSubtitle {{ color: {t['muted_text']}; font-family: Menlo, Monaco, Consolas, monospace; font-size: 13px; letter-spacing: 0.2px; background: transparent; padding-bottom: 2px; }}
        QLabel#sidebarConnectionLabel {{ color: {t['text']}; font-weight: bold; font-size: 15px; background: transparent; padding: 8px 12px 0px 12px; }}
        QLabel#sidebarDeviceLabel {{ color: {t['muted_text']}; font-size: 13px; background: transparent; padding: 0px 12px 8px 12px; }}
        QPushButton#sidebarButton {{ text-align: left; border: 0px; background: transparent; color: {t['text']}; padding: 10px 12px; border-radius: 7px; font-size: 15px; }}
        QPushButton#sidebarButton:hover {{ background: {t['button_hover']}; }}
        QPushButton#sidebarButton:disabled {{ color: {t['connected']}; background: {t['hover_bg']}; }}
        QTextEdit#logBox {{ background: {t['log_bg']}; border: 1px solid {t['border']}; border-radius: 6px; color: {t['muted_text']}; font-family: Menlo, Monaco, Consolas, monospace; font-size: 12px; padding: 6px; }}
        QPushButton, QComboBox, QLineEdit {{ background: {t['button_bg']}; color: {t['text']}; border: 1px solid {t['border']}; border-radius: 6px; font-size: 13px; min-height: 32px; padding: 4px 10px; }}
        QPushButton#secondaryButton {{ color: {t['muted_text']}; font-size: 12px; min-width: 84px; max-width: 112px; padding: 1px 8px; }}
        QPushButton:hover, QComboBox:hover {{ background: {t['button_hover']}; }}
        QPushButton:pressed {{ background: {t['button_pressed']}; }}
        QPushButton:disabled {{ color: {t['button_disabled_text']}; background: {t['button_disabled_bg']}; }}
        """

    def lock_plot_axes(self, preserve_x=False):
        """Keep the RF graph's amplitude scale stable.

        pyqtgraph may revisit bounds when data, hover cursors, mic markers,
        top-hit lines, or capture overlays are refreshed. This keeps the
        display locked to RF Bridge's normal dBm view so connecting a tinySA
        does not expand or re-base the vertical axis.
        """
        if not hasattr(self, "plot"):
            return

        view_box = self.plot.getViewBox()
        try:
            view_box.disableAutoRange(axis=view_box.XYAxes)
            view_box.setMouseEnabled(x=True, y=False)
            view_box.setDefaultPadding(0)
            view_box.setLimits(
                yMin=RF_Y_MIN,
                yMax=RF_Y_MAX,
                minYRange=RF_Y_RANGE,
                maxYRange=RF_Y_RANGE,
            )
        except Exception:
            pass

        self.plot.disableAutoRange()
        self.plot.enableAutoRange(x=False, y=False)
        self.plot.setYRange(RF_Y_MIN, RF_Y_MAX, padding=0)
        self.plot.getViewBox().setYRange(RF_Y_MIN, RF_Y_MAX, padding=0)

        if not preserve_x and self.freqs_mhz:
            self.plot.setXRange(min(self.freqs_mhz), max(self.freqs_mhz), padding=0)

        self.update_frequency_bounds()

    def update_frequency_bounds(self, freqs_mhz=None):
        if freqs_mhz is None:
            freqs_mhz = self.freqs_mhz
        if not hasattr(self, "frequency_view_box"):
            return
        if freqs_mhz:
            self.frequency_view_box.set_frequency_bounds((min(freqs_mhz), max(freqs_mhz)))
        else:
            self.frequency_view_box.set_frequency_bounds(None)

    def reset_frequency_view(self):
        freqs_mhz = self.freqs_mhz or self.live_freqs_mhz
        if not freqs_mhz:
            return
        self.plot.setXRange(min(freqs_mhz), max(freqs_mhz), padding=0)
        self.lock_plot_axes(preserve_x=True)
        self.log("Frequency view reset")

    def show_plot_context_menu(self, event):
        from PySide6.QtGui import QCursor

        # pyqtgraph can sometimes replay a context-menu callback after a
        # marker label handled a right-click. Only show this menu for an
        # actual right-click/context event, and swallow immediately following
        # left-click cleanup events so normal marker dragging resumes.
        try:
            button = event.button()
        except Exception:
            button = None
        if button is not None and button != self.Qt.RightButton:
            try:
                event.accept()
            except Exception:
                pass
            return

        if time.monotonic() < getattr(self, "suppress_plot_click_until", 0.0):
            try:
                event.accept()
            except Exception:
                pass
            return

        scene_pos = event.scenePos()
        freq = self.plot_frequency_from_scene_pos(scene_pos)
        menu = self.QMenu(self.window)
        markers_available = self.markers_available()

        if freq is not None and markers_available:
            marker_index, marker = self.nearest_mic_marker(freq)
            if marker is not None:
                edit_action = menu.addAction(f"Edit Marker: {marker['name']}...")
                edit_action.triggered.connect(
                    lambda _checked=False, index=marker_index: self.prompt_edit_mic_marker(index)
                )
                remove_action = menu.addAction(f"Remove Marker: {marker['name']}")
                remove_action.triggered.connect(
                    lambda _checked=False, index=marker_index: self.remove_mic_marker(index)
                )
                menu.addSeparator()

            add_action = menu.addAction(f"Add Mic Marker at {freq:.3f} MHz...")
            add_action.triggered.connect(
                lambda _checked=False, marker_freq=freq: self.prompt_add_mic_marker(marker_freq)
            )

        reset_action = menu.addAction("Reset Frequency Range")
        reset_action.triggered.connect(self.reset_frequency_view)
        menu.exec(QCursor.pos())
        self.suppress_plot_click_until = time.monotonic() + 0.35
        try:
            self.plot.scene().clearFocus()
        except Exception:
            pass

    def create_menus(self):
        file_menu = self.window.menuBar().addMenu("File")

        open_capture_action = self.QAction("Open Capture…", self.window)
        open_capture_action.triggered.connect(self.open_capture)
        file_menu.addAction(open_capture_action)

        return_live_action = self.QAction("Return to Live", self.window)
        return_live_action.triggered.connect(self.return_to_live)
        file_menu.addAction(return_live_action)

        app_menu = self.window.menuBar().addMenu("RF Bridge")
        preferences_action = self.QAction("Preferences…", self.window)
        preferences_action.triggered.connect(self.open_preferences)
        app_menu.addAction(preferences_action)

        open_overlay_action = self.QAction("Open Capture Overlay(s)…", self.window)
        open_overlay_action.triggered.connect(self.open_capture_overlays)
        file_menu.addAction(open_overlay_action)

        clear_overlays_action = self.QAction("Clear Capture Overlays", self.window)
        clear_overlays_action.triggered.connect(self.clear_capture_overlays)
        file_menu.addAction(clear_overlays_action)

        self.overlay_menu = self.window.menuBar().addMenu("Overlays")
        self.rebuild_overlay_menu()

        profiles_menu = self.window.menuBar().addMenu("Profiles")
        new_profile_action = self.QAction("New Gig Profile…", self.window)
        new_profile_action.triggered.connect(self.new_profile)
        profiles_menu.addAction(new_profile_action)

        save_profile_action = self.QAction("Export Current Profile…", self.window)
        save_profile_action.triggered.connect(self.export_profile)
        profiles_menu.addAction(save_profile_action)

        load_profile_action = self.QAction("Import Profile…", self.window)
        load_profile_action.triggered.connect(self.import_profile)
        profiles_menu.addAction(load_profile_action)

        tools_menu = self.window.menuBar().addMenu("Tools")
        mic_plot_action = self.QAction("Markers / Mic Plot…", self.window)
        mic_plot_action.triggered.connect(self.open_mic_plot)
        tools_menu.addAction(mic_plot_action)

        help_menu = self.window.menuBar().addMenu("Help")
        wiki_action = self.QAction("RF Bridge Wiki…", self.window)
        wiki_action.triggered.connect(self.open_wiki)
        help_menu.addAction(wiki_action)

        open_folder_action = self.QAction("Open Scan Folder", self.window)
        open_folder_action.triggered.connect(self.open_scan_folder)
        help_menu.addAction(open_folder_action)

        about_action = self.QAction("About RF Bridge", self.window)
        about_action.triggered.connect(self.open_about)
        help_menu.addAction(about_action)

    def apply_theme(self):
        self.theme_name = self.resolve_theme_name(self.appearance)
        self.theme = THEMES[self.theme_name]
        self.window.setStyleSheet(self.stylesheet())
        self.plot.setBackground(self.theme["plot_bg"])
        axis_pen = self.pg.mkPen(self.theme["axis"])
        self.plot.getAxis("bottom").setPen(axis_pen)
        self.plot.getAxis("left").setPen(axis_pen)
        self.plot.getAxis("bottom").setTextPen(self.theme["axis_text"])
        self.plot.getAxis("left").setTextPen(self.theme["axis_text"])
        self.plot.setTitle(f"RF Bridge - {self.gig_slug}", color=self.theme["text"], size="16pt")
        self.plot.setLabel("left", "dBm", color=self.theme["axis_text"])
        self.update_frequency_range_labels()
        self.update_connection_state(self.connected, self.connection_status.text())
        self.render_mic_markers()
        self.render_capture_overlays()

    def open_capture(self):
        from PySide6.QtWidgets import QFileDialog

        start_dir = self.output_dir if os.path.isdir(self.output_dir) else self.settings.get_storage_root()
        path, _ = QFileDialog.getOpenFileName(
            self.window,
            "Open RF Bridge Capture",
            start_dir,
            "CSV captures (*.csv);;All files (*)",
        )

        if not path:
            return

        try:
            capture = load_capture_csv(path)
        except Exception as exc:
            self.show_error(f"Could not load capture:\n{exc}")
            self.log(f"Capture load failed: {exc}")
            return

        self.loaded_capture = capture
        self.capture_mode = True
        self.frozen = False
        self.freeze_button.setText("Freeze")
        self.return_live_button.setEnabled(bool(self.latest_dbm and self.live_freqs_mhz))
        self.freqs_mhz = capture["freqs_mhz"]
        self.display_dbm = capture["dbm"]
        self.last_cursor_index = None
        self.peak_curve.setData([], [])
        self.peak_hold = None
        self.peak_history = deque()

        self.plot.setXRange(min(self.freqs_mhz), max(self.freqs_mhz), padding=0)
        self.lock_plot_axes(preserve_x=True)
        self.update_frequency_range_labels()
        self.cursor_line.setPos(self.freqs_mhz[0])
        self.render_mic_markers()
        self.live_curve.setData(self.freqs_mhz, self.display_dbm)
        self.update_top_frequencies(self.display_dbm)
        self.plot.setTitle(
            f"RF Bridge - {self.gig_slug} - Loaded Capture: {capture['name']}",
            color=self.theme["text"],
            size="16pt",
        )
        self.log(f"Loaded capture: {capture['name']}")
        self.update_status()

    def return_to_live(self):
        if not self.latest_dbm or not self.live_freqs_mhz:
            self.log("No live trace is available yet")
            return

        self.capture_mode = False
        self.loaded_capture = None
        self.freqs_mhz = self.live_freqs_mhz.copy()
        self.last_cursor_index = None
        self.return_live_button.setEnabled(False)
        self.plot.setXRange(min(self.freqs_mhz), max(self.freqs_mhz), padding=0)
        self.lock_plot_axes(preserve_x=True)
        self.update_frequency_range_labels()
        self.cursor_line.setPos(self.freqs_mhz[0])
        self.render_mic_markers()
        self.render_scan(self.latest_dbm)
        self.log("Returned to live trace")
        self.update_status()

    def add_auto_trace_overlay(self, freqs_mhz, dbm, now=None):
        if now is None:
            now = time.time()
        capture = {
            "name": f"Auto Trace {time_12h()}",
            "path": None,
            "freqs_mhz": list(freqs_mhz),
            "dbm": list(dbm),
            "visible": True,
            "color": self.next_overlay_color(),
            "auto_trace": True,
        }
        self.capture_overlays.append(capture)
        auto_indexes = [
            index
            for index, item in enumerate(self.capture_overlays)
            if item.get("auto_trace")
        ]
        while len(auto_indexes) > MAX_AUTO_TRACE_OVERLAYS:
            remove_index = auto_indexes.pop(0)
            self.capture_overlays.pop(remove_index)
            auto_indexes = [
                index
                for index, item in enumerate(self.capture_overlays)
                if item.get("auto_trace")
            ]
        self.last_auto_trace_time = now
        self.render_capture_overlays()
        self.rebuild_overlay_menu()
        self.log(f"Auto trace overlay added: {capture['name']}")


    def next_overlay_color(self):
        colors = [
            "#33aaff", "#ffaa00", "#cc66ff", "#eeeeee", "#ff3333", "#00ff99",
            "#00e5ff", "#ff7a00", "#ff66cc", "#7cff00", "#b388ff", "#a0a0a0",
        ]
        color = colors[self.overlay_color_index % len(colors)]
        self.overlay_color_index += 1
        return color

    def open_capture_overlays(self):
        from PySide6.QtWidgets import QFileDialog

        start_dir = self.output_dir if os.path.isdir(self.output_dir) else self.settings.get_storage_root()
        paths, _ = QFileDialog.getOpenFileNames(
            self.window,
            "Open RF Bridge Capture Overlay(s)",
            start_dir,
            "CSV captures (*.csv);;All files (*)",
        )

        if not paths:
            return

        loaded = 0
        for path in paths:
            try:
                capture = load_capture_csv(path)
            except Exception as exc:
                self.log(f"Overlay load failed for {os.path.basename(path)}: {exc}")
                continue
            capture["visible"] = True
            capture["color"] = self.next_overlay_color()
            self.capture_overlays.append(capture)
            loaded += 1

        self.render_capture_overlays()
        self.rebuild_overlay_menu()
        self.log(f"Loaded {loaded} capture overlay(s)")
        self.update_status()

    def render_capture_overlays(self):
        active_curves = []
        for capture in self.capture_overlays:
            curve = capture.get("_curve")
            if curve is None:
                curve = self.plot.plot(
                    capture["freqs_mhz"],
                    capture["dbm"],
                    pen=self.pg.mkPen(capture.get("color", "#33aaff"), width=1.3),
                    name=capture.get("name", "Capture"),
                )
                curve.setZValue(2)
                capture["_curve"] = curve
            else:
                curve.setData(capture["freqs_mhz"], capture["dbm"])
                curve.setPen(self.pg.mkPen(capture.get("color", "#33aaff"), width=1.3))
            curve.setVisible(bool(capture.get("visible", True)))
            curve.setZValue(2)
            active_curves.append(curve)

        active_ids = {id(curve) for curve in active_curves}
        for item in self.capture_overlay_items:
            if id(item) in active_ids:
                continue
            try:
                self.plot.removeItem(item)
            except Exception:
                pass
        self.capture_overlay_items = active_curves

    def rebuild_overlay_menu(self):
        if not hasattr(self, "overlay_menu"):
            return
        self.overlay_menu.clear()
        self.capture_overlay_actions = []
        if not self.capture_overlays:
            empty_action = self.QAction("No capture overlays loaded", self.window)
            empty_action.setEnabled(False)
            self.overlay_menu.addAction(empty_action)
            self.rebuild_overlay_panel()
            return
        for index, capture in enumerate(self.capture_overlays):
            action = self.QAction(capture.get("name", f"Capture {index + 1}"), self.window)
            action.setCheckable(True)
            action.setChecked(bool(capture.get("visible", True)))
            action.toggled.connect(lambda checked, i=index: self.set_overlay_visible(i, checked))
            self.overlay_menu.addAction(action)
            self.capture_overlay_actions.append(action)
        self.overlay_menu.addSeparator()
        clear_action = self.QAction("Clear Capture Overlays", self.window)
        clear_action.triggered.connect(self.clear_capture_overlays)
        self.overlay_menu.addAction(clear_action)
        self.rebuild_overlay_panel()

    def rebuild_overlay_panel(self):
        from PySide6.QtWidgets import QLabel, QCheckBox

        if not hasattr(self, "overlay_controls_row"):
            return

        while self.overlay_controls_row.count():
            item = self.overlay_controls_row.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)

        self.overlay_checkbox_widgets = []
        self.overlay_checkbox_indexes = []
        if not self.capture_overlays:
            self.overlay_empty_label = QLabel("No overlays loaded")
            self.overlay_empty_label.setObjectName("overlayEmptyLabel")
            self.overlay_empty_label.setAlignment(self.Qt.AlignCenter)
            self.overlay_controls_row.addWidget(self.overlay_empty_label, 0, 0, 1, 2)
            if hasattr(self, "overlay_empty_hint"):
                self.overlay_empty_hint.setVisible(True)
            return

        if hasattr(self, "overlay_empty_hint"):
            self.overlay_empty_hint.setVisible(False)

        max_visible_controls = 10
        columns = 2
        visible_controls = list(enumerate(self.capture_overlays[:max_visible_controls]))
        row = 0
        for daypart in ("Morning", "Afternoon", "Evening", "Overnight", "Other"):
            daypart_items = [
                (index, capture)
                for index, capture in visible_controls
                if capture_overlay_daypart(capture.get("name")) == daypart
            ]
            if not daypart_items:
                continue

            if row > 0:
                row += 1
            heading = QLabel(daypart)
            heading.setObjectName("overlaySubtitle")
            self.overlay_controls_row.addWidget(heading, row, 0, 1, columns)
            row += 1

            for item_index, (index, capture) in enumerate(daypart_items):
                label = compact_capture_label(capture.get("name", f"Capture {index + 1}"))
                checkbox = QCheckBox(label)
                checkbox.setToolTip(capture.get("name", label))
                checkbox.setChecked(bool(capture.get("visible", True)))
                checkbox.setStyleSheet(f"color: {capture.get('color', self.theme['text'])};")
                checkbox.toggled.connect(lambda checked, i=index: self.set_overlay_visible(i, checked))
                column = item_index % columns
                self.overlay_controls_row.addWidget(checkbox, row, column)
                self.overlay_checkbox_widgets.append(checkbox)
                self.overlay_checkbox_indexes.append(index)
                if column == columns - 1:
                    row += 1

            if daypart_items and (len(daypart_items) % columns):
                row += 1

        if len(self.capture_overlays) > max_visible_controls:
            more_label = QLabel(f"+{len(self.capture_overlays) - max_visible_controls} more in Overlays menu")
            more_label.setObjectName("overlayEmptyLabel")
            self.overlay_controls_row.addWidget(more_label, row, 0, 1, columns)

        for column in range(columns):
            self.overlay_controls_row.setColumnStretch(column, 1)

    def sync_overlay_controls(self):
        """Keep overlay menu actions and panel checkboxes in sync without rebuilding.

        Rebuilding the overlay panel from inside a checkbox/menu toggle can delete
        the widget that emitted the signal while Qt is still processing it. On
        macOS that can crash the app. Sync the existing controls instead.
        """
        for index, action in enumerate(getattr(self, "capture_overlay_actions", [])):
            if index >= len(self.capture_overlays):
                continue
            action.blockSignals(True)
            action.setChecked(bool(self.capture_overlays[index].get("visible", True)))
            action.blockSignals(False)

        for index, checkbox in zip(
            getattr(self, "overlay_checkbox_indexes", []),
            getattr(self, "overlay_checkbox_widgets", []),
        ):
            if index >= len(self.capture_overlays):
                continue
            checkbox.blockSignals(True)
            checkbox.setChecked(bool(self.capture_overlays[index].get("visible", True)))
            checkbox.blockSignals(False)

    def set_overlay_visible(self, index, visible):
        if 0 <= index < len(self.capture_overlays):
            self.capture_overlays[index]["visible"] = bool(visible)
            self.render_capture_overlays()
            self.sync_overlay_controls()
            self.update_status()

    def clear_capture_overlays(self):
        for item in self.capture_overlay_items:
            try:
                self.plot.removeItem(item)
            except Exception:
                pass
        self.capture_overlays = []
        self.capture_overlay_items = []
        self.rebuild_overlay_menu()
        self.log("Capture overlays cleared")
        self.update_status()

    def new_profile(self):
        from PySide6.QtWidgets import QFileDialog, QInputDialog
        from .utils import safe_name

        gig_name, ok = QInputDialog.getText(self.window, "New Gig Profile", "Session Name:", text="")
        if not ok:
            return
        gig_name = gig_name.strip()
        if not gig_name:
            self.show_error("Session Name is required.")
            return

        storage_root = QFileDialog.getExistingDirectory(
            self.window,
            "Choose RF Bridge Storage Location",
            self.settings.get_storage_root(),
        ) or self.settings.get_storage_root()

        self.gig_slug = safe_name(gig_name)
        self.output_dir = os.path.join(storage_root, "wwb_scans", self.gig_slug)
        os.makedirs(self.output_dir, exist_ok=True)
        self.settings.set_storage_root(storage_root)
        self.clear_capture_overlays()
        self.loaded_capture = None
        self.capture_mode = False
        self.return_live_button.setEnabled(False)
        self.plot.setTitle(f"RF Bridge - {self.gig_slug}", color=self.theme["text"], size="16pt")
        self.log(f"Profile switched to: {self.gig_slug}")
        self.update_status()

    def export_profile(self):
        from PySide6.QtWidgets import QFileDialog

        profile = {
            "version": 1,
            "app_version": __version__,
            "gig_slug": self.gig_slug,
            "output_dir": self.output_dir,
            "storage_root": self.settings.get_storage_root(),
            "refresh_seconds": self.refresh_seconds,
            "appearance": self.appearance,
            "markers": self.mic_markers,
            "capture_overlays": [capture.get("path") for capture in self.capture_overlays if capture.get("path")],
        }

        default_path = os.path.join(self.settings.get_storage_root(), f"{self.gig_slug}.rfbridge-profile.json")
        path, _ = QFileDialog.getSaveFileName(
            self.window,
            "Export RF Bridge Profile",
            default_path,
            "RF Bridge Profile (*.rfbridge-profile.json);;JSON files (*.json);;All files (*)",
        )
        if not path:
            return
        with open(path, "w", encoding="utf-8") as file:
            json.dump(profile, file, indent=2)
        self.log(f"Profile exported: {os.path.basename(path)}")

    def import_profile(self):
        from PySide6.QtWidgets import QFileDialog

        path, _ = QFileDialog.getOpenFileName(
            self.window,
            "Import RF Bridge Profile",
            self.settings.get_storage_root(),
            "RF Bridge Profile (*.rfbridge-profile.json);;JSON files (*.json);;All files (*)",
        )
        if not path:
            return

        try:
            with open(path, "r", encoding="utf-8") as file:
                profile = json.load(file)
        except Exception as exc:
            self.show_error(f"Could not import profile:\n{exc}")
            return

        self.gig_slug = str(profile.get("gig_slug") or self.gig_slug)
        self.output_dir = str(profile.get("output_dir") or self.output_dir)
        os.makedirs(self.output_dir, exist_ok=True)
        storage_root = profile.get("storage_root")
        if storage_root:
            self.settings.set_storage_root(str(storage_root))
        self.mic_markers = save_markers(self.settings, profile.get("markers", []))
        self.set_refresh_interval(float(profile.get("refresh_seconds", self.refresh_seconds)))
        self.appearance = str(profile.get("appearance", self.appearance))
        self.settings.set_appearance(self.appearance)
        self.apply_theme()
        self.clear_capture_overlays()
        for capture_path in profile.get("capture_overlays", []):
            try:
                capture = load_capture_csv(capture_path)
                capture["visible"] = True
                capture["color"] = self.next_overlay_color()
                self.capture_overlays.append(capture)
            except Exception as exc:
                self.log(f"Could not reload overlay {capture_path}: {exc}")
        self.render_capture_overlays()
        self.rebuild_overlay_menu()
        self.render_mic_markers()
        self.plot.setTitle(f"RF Bridge - {self.gig_slug}", color=self.theme["text"], size="16pt")
        self.log(f"Profile imported: {os.path.basename(path)}")
        self.update_status()

    def open_about(self):
        self.QMessageBox.about(
            self.window,
            "About RF Bridge",
            f"RF Bridge v{__version__}<br><br>tinySA → WWB bridge and live RF visualization utility for macOS.<br><br>Built for live sound engineers, RF coordinators, and wireless techs.",
        )

    def open_wiki(self):
        webbrowser.open("https://github.com/sweenster247/RF_Bridge/wiki")
        self.log("Opened RF Bridge wiki")

    def open_scan_folder(self):
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtCore import QUrl
        os.makedirs(self.output_dir, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(self.output_dir))
        self.log("Opened scan folder")

    def open_mic_plot(self):
        from PySide6.QtWidgets import (
            QCheckBox,
            QComboBox,
            QDialog,
            QDialogButtonBox,
            QDoubleSpinBox,
            QHBoxLayout,
            QLineEdit,
            QPushButton,
            QTableWidget,
            QTableWidgetItem,
            QVBoxLayout,
        )

        dialog = QDialog(self.window)
        dialog.setWindowTitle("Markers / Mic Plot")
        dialog.setMinimumSize(720, 420)

        layout = QVBoxLayout(dialog)
        table = QTableWidget(0, 4)
        table.setHorizontalHeaderLabels(["Visible", "Name", "Frequency MHz", "Color"])
        table.horizontalHeader().setStretchLastSection(True)
        table.verticalHeader().setVisible(False)

        def color_name_for(value):
            for name, color in MARKER_COLORS:
                if color.lower() == str(value).lower():
                    return name
            return "Green"

        def add_row(marker=None):
            marker = marker or {
                "name": "",
                "frequency_mhz": 500.000,
                "color": DEFAULT_MARKER_COLOR,
                "visible": True,
            }
            row = table.rowCount()
            table.insertRow(row)

            visible = QCheckBox()
            visible.setChecked(bool(marker.get("visible", True)))
            table.setCellWidget(row, 0, visible)

            name = QLineEdit(str(marker.get("name", "")))
            name.setPlaceholderText("Vocal 1")
            table.setCellWidget(row, 1, name)

            frequency = QDoubleSpinBox()
            frequency.setRange(1.0, 6000.0)
            frequency.setDecimals(3)
            frequency.setSingleStep(0.025)
            frequency.setValue(float(marker.get("frequency_mhz", 500.000)))
            table.setCellWidget(row, 2, frequency)

            color = QComboBox()
            for color_name, color_value in MARKER_COLORS:
                color.addItem(color_name, color_value)
            index = color.findText(color_name_for(marker.get("color", DEFAULT_MARKER_COLOR)))
            color.setCurrentIndex(max(index, 0))
            table.setCellWidget(row, 3, color)

        for marker in self.mic_markers:
            add_row(marker)

        add_button = QPushButton("Add Marker")
        remove_button = QPushButton("Remove Selected")
        button_row = QHBoxLayout()
        button_row.addWidget(add_button)
        button_row.addWidget(remove_button)
        button_row.addStretch(1)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)

        def remove_selected():
            rows = sorted({index.row() for index in table.selectedIndexes()}, reverse=True)
            for row in rows:
                table.removeRow(row)

        add_button.clicked.connect(add_row)
        remove_button.clicked.connect(remove_selected)

        layout.addWidget(table)
        layout.addLayout(button_row)
        layout.addWidget(buttons)
        dialog.setStyleSheet(self.stylesheet())

        if dialog.exec() != QDialog.Accepted:
            return

        markers = []
        try:
            for row in range(table.rowCount()):
                name_widget = table.cellWidget(row, 1)
                freq_widget = table.cellWidget(row, 2)
                color_widget = table.cellWidget(row, 3)
                visible_widget = table.cellWidget(row, 0)
                name = name_widget.text().strip() if name_widget else ""
                if not name:
                    continue
                markers.append({
                    "name": name,
                    "frequency_mhz": freq_widget.value(),
                    "color": color_widget.currentData(),
                    "visible": visible_widget.isChecked(),
                })
            self.mic_markers = save_markers(self.settings, markers)
        except ValueError as exc:
            self.show_error(str(exc))
            return

        self.render_mic_markers()
        self.log(f"Mic plot updated: {len(self.mic_markers)} marker(s)")

    def plot_frequency_from_scene_pos(self, scene_pos):
        if not getattr(self, "plot", None):
            return None

        plot_item = self.plot.getPlotItem()
        view_box = plot_item.vb
        if not view_box.sceneBoundingRect().contains(scene_pos):
            return None

        mouse_point = view_box.mapSceneToView(scene_pos)
        freq = float(mouse_point.x())
        if self.freqs_mhz:
            freq = max(min(self.freqs_mhz), min(max(self.freqs_mhz), freq))
        return snap_display_frequency(freq)

    def nearest_mic_marker(self, freq_mhz):
        if not self.markers_available():
            return None, None
        visible_markers = [
            (index, marker)
            for index, marker in enumerate(self.mic_markers)
            if marker.get("visible", True)
        ]
        if not visible_markers:
            return None, None

        nearest_index, nearest_marker = min(
            visible_markers,
            key=lambda item: abs(float(item[1]["frequency_mhz"]) - freq_mhz),
        )
        if self.freqs_mhz:
            span = max(self.freqs_mhz) - min(self.freqs_mhz)
        else:
            span = 0
        hit_radius = max(MIC_MARKER_HIT_RADIUS_MHZ, span * 0.003)
        if abs(float(nearest_marker["frequency_mhz"]) - freq_mhz) <= hit_radius:
            return nearest_index, nearest_marker
        return None, None

    def on_plot_mouse_click(self, event):
        if time.monotonic() < getattr(self, "suppress_plot_click_until", 0.0):
            event.accept()
            return
        if event.button() != self.Qt.RightButton:
            return
        event.accept()
        self.show_plot_context_menu(event)

    def show_mic_marker_context_menu(self, freq_mhz, marker_index=None, marker=None):
        from PySide6.QtGui import QCursor

        if not self.markers_available():
            return

        menu = self.QMenu(self.window)
        if marker is not None:
            edit_action = menu.addAction(f"Edit Marker: {marker['name']}...")
            edit_action.triggered.connect(
                lambda _checked=False, index=marker_index: self.prompt_edit_mic_marker(index)
            )
            remove_action = menu.addAction(f"Remove Marker: {marker['name']}")
            remove_action.triggered.connect(
                lambda _checked=False, index=marker_index: self.remove_mic_marker(index)
            )
            menu.addSeparator()

        add_action = menu.addAction(f"Add Mic Marker at {freq_mhz:.3f} MHz...")
        add_action.triggered.connect(
            lambda _checked=False, marker_freq=freq_mhz: self.prompt_add_mic_marker(marker_freq)
        )
        menu.exec(QCursor.pos())
        self.suppress_plot_click_until = time.monotonic() + 0.35
        try:
            self.plot.scene().clearFocus()
        except Exception:
            pass

    def on_mic_marker_label_click(self, event, marker_index, freq_mhz):
        if not self.markers_available():
            event.accept()
            return
        # Always accept marker-label clicks so they do not leak into the plot
        # scene and get interpreted as a stale context-menu request. Left-click
        # stays available for normal selection/drag behavior; right-click opens
        # the marker menu.
        event.accept()
        if event.button() != self.Qt.RightButton:
            return

        self.suppress_plot_click_until = time.monotonic() + 0.35
        marker = None
        if 0 <= marker_index < len(self.mic_markers):
            marker = self.mic_markers[marker_index]
        self.show_mic_marker_context_menu(freq_mhz, marker_index, marker)

    def prompt_add_mic_marker(self, freq_mhz):
        from PySide6.QtWidgets import QInputDialog

        name, ok = QInputDialog.getText(
            self.window,
            "Add Mic Marker",
            f"Marker name for {freq_mhz:.3f} MHz:",
            text="",
        )
        if not ok:
            return

        name = name.strip()
        if not name:
            self.show_error("Marker name is required.")
            return

        color = MARKER_COLORS[len(self.mic_markers) % len(MARKER_COLORS)][1]
        try:
            self.mic_markers = save_markers(
                self.settings,
                self.mic_markers + [{
                    "name": name,
                    "frequency_mhz": freq_mhz,
                    "color": color,
                    "visible": True,
                }],
            )
        except ValueError as exc:
            self.show_error(str(exc))
            return

        self.render_mic_markers()
        self.log(f"Mic marker added: {name} at {freq_mhz:.3f} MHz")

    def prompt_edit_mic_marker(self, marker_index):
        if not (0 <= marker_index < len(self.mic_markers)):
            return

        from PySide6.QtWidgets import (
            QCheckBox,
            QComboBox,
            QDialog,
            QDialogButtonBox,
            QDoubleSpinBox,
            QFormLayout,
            QLineEdit,
            QVBoxLayout,
        )

        marker = dict(self.mic_markers[marker_index])
        dialog = QDialog(self.window)
        dialog.setWindowTitle("Edit Mic Marker")
        layout = QVBoxLayout(dialog)
        form = QFormLayout()

        name = QLineEdit(str(marker.get("name", "")))
        frequency = QDoubleSpinBox()
        frequency.setRange(1.000, 2000.000)
        frequency.setDecimals(3)
        frequency.setSingleStep(FREQUENCY_DISPLAY_STEP_MHZ)
        frequency.setValue(float(marker.get("frequency_mhz", 500.000)))

        color = QComboBox()
        for color_name, color_value in MARKER_COLORS:
            color.addItem(color_name, color_value)
        current_color = marker.get("color", DEFAULT_MARKER_COLOR)
        color_index = color.findData(current_color)
        if color_index >= 0:
            color.setCurrentIndex(color_index)

        visible = QCheckBox("Show marker")
        visible.setChecked(bool(marker.get("visible", True)))

        form.addRow("Name", name)
        form.addRow("Frequency", frequency)
        form.addRow("Color", color)
        form.addRow("Visible", visible)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() != QDialog.Accepted:
            return

        updated_marker = {
            "name": name.text().strip(),
            "frequency_mhz": float(frequency.value()),
            "color": color.currentData() or DEFAULT_MARKER_COLOR,
            "visible": visible.isChecked(),
        }
        updated = list(self.mic_markers)
        updated[marker_index] = updated_marker
        try:
            self.mic_markers = save_markers(self.settings, updated)
        except ValueError as exc:
            self.show_error(str(exc))
            return

        self.render_mic_markers()
        self.log(
            f"Mic marker updated: {updated_marker['name']} "
            f"at {updated_marker['frequency_mhz']:.3f} MHz"
        )

    def remove_mic_marker(self, marker_index):
        if not (0 <= marker_index < len(self.mic_markers)):
            return

        marker = self.mic_markers[marker_index]
        self.mic_markers = save_markers(
            self.settings,
            [
                item
                for index, item in enumerate(self.mic_markers)
                if index != marker_index
            ],
        )
        self.render_mic_markers()
        self.log(f"Mic marker removed: {marker['name']}")

    def mic_marker_label_positions(self, visible_markers):
        placements = {}
        if self.freqs_mhz:
            span = max(self.freqs_mhz) - min(self.freqs_mhz)
        else:
            marker_freqs = [float(marker["frequency_mhz"]) for _index, marker in visible_markers]
            span = max(marker_freqs) - min(marker_freqs) if marker_freqs else 0
        view_low, view_high = self.plot.getViewBox().viewRange()[0] if getattr(self, "plot", None) else (0, span)
        view_span = max(view_high - view_low, span, 1.0)
        plot_width = max(getattr(self.plot, "width", lambda: 900)(), 1) if getattr(self, "plot", None) else 900
        minimum_gap = max(MIC_MARKER_LABEL_MIN_GAP_MHZ, span * MIC_MARKER_LABEL_GAP_RATIO)
        lane_intervals = [[] for _lane in MIC_MARKER_LABEL_LANES]

        def estimated_label_half_width(marker):
            freq = float(marker["frequency_mhz"])
            label_lines = [str(marker.get("name", "")), f"{freq:.3f} MHz"]
            character_count = max(len(line) for line in label_lines)
            estimated_pixels = max(88, (character_count * 8) + MIC_MARKER_LABEL_PIXEL_PADDING)
            return max(minimum_gap / 2, (estimated_pixels / plot_width) * view_span / 2)

        for index, marker in sorted(
            visible_markers,
            key=lambda item: float(item[1]["frequency_mhz"]),
        ):
            freq = float(marker["frequency_mhz"])
            label_x = self.clamped_mic_marker_label_x(freq)
            half_width = estimated_label_half_width(marker)
            interval = (label_x - half_width, label_x + half_width)
            lane_index = 0
            for candidate, intervals in enumerate(lane_intervals):
                if all(interval[0] > existing[1] or interval[1] < existing[0] for existing in intervals):
                    lane_index = candidate
                    break
            else:
                lane_index = min(
                    range(len(lane_intervals)),
                    key=lambda candidate: len(lane_intervals[candidate]),
                )
            lane_intervals[lane_index].append(interval)
            placements[index] = MIC_MARKER_LABEL_LANES[lane_index]

        return placements

    def clamped_mic_marker_label_x(self, freq):
        if not getattr(self, "plot", None):
            return freq

        view_low, view_high = self.plot.getViewBox().viewRange()[0]
        if view_high <= view_low:
            return freq

        width = view_high - view_low
        margin = min(width * 0.04, width / 3)
        return max(view_low + margin, min(view_high - margin, freq))

    def update_mic_marker_label_view_positions(self, *args):
        visible_markers = [
            (index, marker)
            for index, marker in enumerate(self.mic_markers)
            if marker.get("visible", True)
        ]
        label_positions = self.mic_marker_label_positions(visible_markers)
        for item in getattr(self, "mic_marker_label_items", []):
            label = item.get("label")
            if label is None:
                continue
            item["y"] = label_positions.get(item.get("index"), item["y"])
            label.setPos(
                self.clamped_mic_marker_label_x(item["freq"]),
                item["y"],
            )

    def on_mic_marker_label_drag(self, event, marker_index):
        if not self.markers_available():
            event.accept()
            return
        if event.button() != self.Qt.LeftButton:
            return

        event.accept()
        if not (0 <= marker_index < len(self.mic_markers)):
            return

        freq = self.plot_frequency_from_scene_pos(event.scenePos())
        if freq is None:
            return

        label_item = None
        for item in getattr(self, "mic_marker_label_items", []):
            if item.get("index") == marker_index:
                label_item = item
                break

        line = label_item.get("line") if label_item else None
        if line is not None:
            line.setValue(freq)
        else:
            marker = self.mic_markers[marker_index]
            marker["frequency_mhz"] = freq
            self.on_mic_marker_dragged(marker_index, None)

        if event.isFinish():
            if line is not None:
                self.finish_mic_marker_drag(marker_index, line)
            else:
                marker = dict(self.mic_markers[marker_index])
                marker["frequency_mhz"] = freq
                updated = list(self.mic_markers)
                updated[marker_index] = marker
                try:
                    self.mic_markers = save_markers(self.settings, updated)
                except ValueError as exc:
                    self.show_error(str(exc))
                    self.render_mic_markers()

    def markers_available(self):
        return bool((self.connected or self.demo_mode) and self.freqs_mhz)

    def render_mic_markers(self):
        for item in self.mic_marker_items:
            try:
                self.plot.removeItem(item)
            except Exception:
                pass
        self.mic_marker_items = []
        self.mic_marker_label_items = []

        if not getattr(self, "plot", None):
            return
        if not self.markers_available():
            return

        visible_markers = [
            (index, marker)
            for index, marker in enumerate(self.mic_markers)
            if marker.get("visible", True)
        ]
        label_positions = self.mic_marker_label_positions(visible_markers)

        for index, marker in visible_markers:
            if not marker.get("visible", True):
                continue
            freq = float(marker["frequency_mhz"])
            color = marker.get("color", DEFAULT_MARKER_COLOR)
            marker_bounds = None
            if self.freqs_mhz:
                marker_bounds = (min(self.freqs_mhz), max(self.freqs_mhz))
            line = self.pg.InfiniteLine(
                pos=freq,
                angle=90,
                pen=self.pg.mkPen(color, width=1.5),
                movable=True,
                bounds=marker_bounds,
            )
            line.setZValue(5)
            line.sigPositionChanged.connect(
                lambda item, marker_index=index: self.on_mic_marker_dragged(marker_index, item)
            )
            line.sigPositionChangeFinished.connect(
                lambda item, marker_index=index: self.finish_mic_marker_drag(marker_index, item)
            )
            label = self.pg.TextItem(
                text=f"{marker['name']}\n{freq:.3f} MHz",
                color=color,
                anchor=(0.5, 0.0),
                fill=self.pg.mkBrush(0, 0, 0, 150),
                border=self.pg.mkPen(color, width=0.75),
            )
            # Place mic plot labels slightly below the top of the graph so
            # labels remain visible instead of clipping against the title area.
            # Nearby markers use staggered lanes so labels stay readable.
            label_y = label_positions.get(index, MIC_MARKER_LABEL_LANES[0])
            label.setPos(self.clamped_mic_marker_label_x(freq), label_y)
            label.setZValue(20)
            label.setAcceptedMouseButtons(self.Qt.LeftButton | self.Qt.RightButton)
            label.mouseClickEvent = (
                lambda event, marker_index=index, marker_freq=freq:
                self.on_mic_marker_label_click(event, marker_index, marker_freq)
            )
            label.mouseDragEvent = (
                lambda event, marker_index=index:
                self.on_mic_marker_label_drag(event, marker_index)
            )
            self.plot.addItem(line, ignoreBounds=True)
            self.plot.addItem(label, ignoreBounds=True)
            self.mic_marker_items.extend([line, label])
            self.mic_marker_label_items.append({
                "label": label,
                "line": line,
                "freq": freq,
                "y": label_y,
                "index": index,
            })

    def marker_drag_frequency(self, line_item):
        freq = float(line_item.value())
        if self.freqs_mhz:
            freq = max(min(self.freqs_mhz), min(max(self.freqs_mhz), freq))
        return snap_display_frequency(freq)

    def on_mic_marker_dragged(self, marker_index, line_item):
        if not (0 <= marker_index < len(self.mic_markers)):
            return
        if line_item is not None:
            freq = self.marker_drag_frequency(line_item)
        else:
            freq = snap_display_frequency(float(self.mic_markers[marker_index]["frequency_mhz"]))
        marker = self.mic_markers[marker_index]
        for item in getattr(self, "mic_marker_label_items", []):
            if item.get("index") != marker_index:
                continue
            item["freq"] = freq
            label = item["label"]
            label.setText(f"{marker['name']}\n{freq:.3f} MHz")
            self.update_mic_marker_label_view_positions()
            break

    def finish_mic_marker_drag(self, marker_index, line_item):
        if not (0 <= marker_index < len(self.mic_markers)):
            return
        freq = self.marker_drag_frequency(line_item)
        marker = dict(self.mic_markers[marker_index])
        old_freq = float(marker.get("frequency_mhz", freq))
        marker["frequency_mhz"] = freq
        updated = list(self.mic_markers)
        updated[marker_index] = marker
        try:
            self.mic_markers = save_markers(self.settings, updated)
        except ValueError as exc:
            self.show_error(str(exc))
            self.render_mic_markers()
            return
        self.render_mic_markers()
        if abs(old_freq - freq) >= FREQUENCY_DISPLAY_STEP_MHZ:
            self.log(f"Mic marker moved: {marker['name']} {old_freq:.3f} MHz → {freq:.3f} MHz")

    def open_preferences(self):
        from PySide6.QtWidgets import (
            QCheckBox,
            QComboBox,
            QDialog,
            QDialogButtonBox,
            QDoubleSpinBox,
            QFileDialog,
            QFormLayout,
            QHBoxLayout,
            QLabel,
            QLineEdit,
            QPushButton,
            QVBoxLayout,
        )

        dialog = QDialog(self.window)
        dialog.setWindowTitle("RF Bridge Preferences")
        dialog.setMinimumWidth(520)

        layout = QVBoxLayout(dialog)
        form = QFormLayout()

        appearance_combo = QComboBox()
        appearance_combo.addItems(APPEARANCE_OPTIONS)
        appearance_combo.setCurrentText(self.appearance if self.appearance in APPEARANCE_OPTIONS else "Dark")

        refresh_combo = QComboBox()
        for value in REFRESH_MODES:
            refresh_combo.addItem(f"{format_seconds(value)} seconds", value)

        filename_time_combo = QComboBox()
        filename_time_combo.addItem("12-hour time, e.g. 09-15PM", "12-hour")
        filename_time_combo.addItem("24-hour time, e.g. 21-15", "24-hour")
        filename_time_index = filename_time_combo.findData(self.filename_time_format)
        if filename_time_index < 0:
            filename_time_index = 0
        filename_time_combo.setCurrentIndex(filename_time_index)
        refresh_index = refresh_combo.findData(self.refresh_seconds)
        if refresh_index < 0:
            refresh_combo.addItem(f"Custom ({format_seconds(self.refresh_seconds)} seconds)", self.refresh_seconds)
            refresh_index = refresh_combo.findData(self.refresh_seconds)
        if refresh_index >= 0:
            refresh_combo.setCurrentIndex(refresh_index)

        storage_edit = QLineEdit(self.settings.get_storage_root())
        browse_button = QPushButton("Browse…")
        storage_row = QHBoxLayout()
        storage_row.addWidget(storage_edit, stretch=1)
        storage_row.addWidget(browse_button)

        auto_trace_checkbox = QCheckBox("Add current live trace to overlays automatically")
        auto_trace_checkbox.setChecked(self.auto_trace_enabled)
        auto_trace_minutes = QDoubleSpinBox()
        auto_trace_minutes.setRange(1.0, 120.0)
        auto_trace_minutes.setDecimals(1)
        auto_trace_minutes.setSingleStep(1.0)
        auto_trace_minutes.setSuffix(" min")
        auto_trace_minutes.setValue(self.auto_trace_minutes)

        def choose_folder():
            selected = QFileDialog.getExistingDirectory(
                dialog,
                "Choose Default RF Bridge Storage Location",
                storage_edit.text() or self.settings.default_storage_root(),
            )
            if selected:
                storage_edit.setText(selected)

        browse_button.clicked.connect(choose_folder)

        form.addRow("Appearance", appearance_combo)
        form.addRow("Default refresh", refresh_combo)
        form.addRow("Capture filename time", filename_time_combo)
        form.addRow("Default storage", storage_row)
        form.addRow("Auto trace overlays", auto_trace_checkbox)
        form.addRow("Auto trace interval", auto_trace_minutes)

        note = QLabel(
            "Storage changes apply to new app sessions. Auto trace overlays use the live scan in memory and do not create extra CSV files."
        )
        note.setWordWrap(True)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)

        layout.addLayout(form)
        layout.addWidget(note)
        layout.addWidget(buttons)
        dialog.setStyleSheet(self.stylesheet())

        if dialog.exec() != QDialog.Accepted:
            return

        self.appearance = appearance_combo.currentText()
        self.settings.set_appearance(self.appearance)
        self.settings.set_storage_root(storage_edit.text().strip() or self.settings.default_storage_root())
        self.auto_trace_enabled = auto_trace_checkbox.isChecked()
        self.auto_trace_minutes = float(auto_trace_minutes.value())
        self.filename_time_format = filename_time_combo.currentData() or "12-hour"
        self.settings.set("auto_trace_enabled", self.auto_trace_enabled)
        self.settings.set("auto_trace_minutes", self.auto_trace_minutes)
        self.settings.set_filename_time_format(self.filename_time_format)
        self.set_refresh_interval(float(refresh_combo.currentData()))
        self.apply_theme()
        self.log(
            f"Preferences saved: appearance={self.appearance}, "
            f"storage={self.settings.get_storage_root()}, "
            f"auto_trace={'on' if self.auto_trace_enabled else 'off'}, "
            f"filename_time={self.filename_time_format}"
        )

    def log(self, message):
        self.log_box.append(f"[{time_12h()}] {message}")

    def populate_ports(self):
        current = self.port_combo.currentData() or self.selected_port
        self.port_combo.clear()
        self.port_map = {}
        self.port_combo.addItem("Demo Mode — simulated RF scan", DEMO_PORT)
        ports = candidate_serial_ports()
        for port in ports:
            label = describe_port(port)
            self.port_combo.addItem(label, port.device)
            self.port_map[port.device] = label
        if not ports:
            self.port_combo.addItem("No serial ports found", None)
        if current:
            index = self.port_combo.findData(current)
            if index < 0:
                self.port_combo.addItem(f"Manual: {current}", current)
                index = self.port_combo.findData(current)
            if index >= 0:
                self.port_combo.setCurrentIndex(index)
        self.log(f"Found {len(ports)} serial port(s)")

    def try_auto_connect(self):
        self.start_auto_detect()

    def mark_port_selection_touched(self, _index=None):
        self.port_selection_touched = True

    def start_auto_detect(self):
        if (
            self.auto_detect_thread is not None
            or self.connected
            or self.demo_mode
            or self.shutting_down
        ):
            return

        self.auto_detect_thread = self.QThread()
        self.auto_detect_worker = AutoDetectWorkerFactory.create()
        self.auto_detect_worker.moveToThread(self.auto_detect_thread)
        self.auto_detect_thread.started.connect(self.auto_detect_worker.start)
        self.auto_detect_worker.detected.connect(self.on_auto_detected)
        self.auto_detect_worker.skipped.connect(self.on_auto_detect_skipped)
        self.auto_detect_worker.finished.connect(self.auto_detect_thread.quit)
        self.auto_detect_thread.finished.connect(self.auto_detect_worker.deleteLater)
        self.auto_detect_thread.finished.connect(self.auto_detect_thread.deleteLater)
        self.auto_detect_thread.finished.connect(self.clear_auto_detect_refs)
        self.auto_detect_thread.start()

    def on_auto_detected(self, port, _header, _scanned):
        if self.connected or self.demo_mode or self.worker is not None or self.shutting_down:
            self.log(f"Auto-detected tinySA: {port}; leaving current session unchanged")
            return

        current = self.port_combo.currentData()
        if self.port_selection_touched and current != port:
            self.log(f"Auto-detected tinySA: {port}; leaving selected port unchanged")
            return

        index = self.port_combo.findData(port)
        if index < 0:
            self.port_combo.addItem(f"Manual: {port}", port)
            index = self.port_combo.findData(port)
        if index < 0:
            self.log(f"Auto-detected tinySA: {port}; select it manually to connect")
            return
        self.port_combo.setCurrentIndex(index)
        self.log(f"Auto-detected tinySA: {port}")
        self.auto_connect_in_progress = True
        self.connect_device()

    def on_auto_detect_skipped(self, message):
        self.log(f"Auto-detect skipped: {message}")

    def clear_auto_detect_refs(self):
        self.auto_detect_worker = None
        self.auto_detect_thread = None

    def connect_device(self):
        if self.connected:
            return
        port = self.port_combo.currentData()
        if not port:
            self.show_error("No serial port selected.")
            return
        self.clear_device_notice()

        if port == DEMO_PORT:
            self.start_demo_mode()
            return

        self.selected_port = port
        self.settings.set("last_port", port)
        self.force_disconnected_actions = False
        self.pending_disconnect_status = None
        self.scan_mismatch_count = 0
        self.worker_thread = self.QThread()
        self.worker = ScanWorker(port, self.refresh_seconds, debug_serial=self.debug_serial)
        self.worker.moveToThread(self.worker_thread)
        self.worker_thread.started.connect(self.worker.start)
        self.worker.connected.connect(self.ui_bridge.connected)
        self.worker.scan_ready.connect(self.ui_bridge.scan_ready)
        self.worker.error.connect(self.ui_bridge.error)
        self.worker.reconnecting.connect(self.ui_bridge.reconnecting)
        self.worker.log.connect(self.ui_bridge.log)
        self.worker.disconnected.connect(self.ui_bridge.disconnected)
        self.worker.disconnected.connect(self.worker_thread.quit)
        self.worker_thread.finished.connect(self.worker.deleteLater)
        self.worker_thread.finished.connect(self.worker_thread.deleteLater)
        self.worker_thread.finished.connect(self.clear_worker_refs)
        self.update_connection_state(False, "Connecting…")
        self.worker_thread.start()
        self.log(f"Connecting to {port}")

    def disconnect_device(self):
        if self.demo_mode:
            self.stop_demo_mode()
            return

        if self.worker is not None:
            self.QMetaObject.invokeMethod(
                self.worker,
                "stop",
                self.Qt.QueuedConnection,
            )
        else:
            self.on_disconnected()

    def clear_worker_refs(self):
        self.worker = None
        self.worker_thread = None
        if not self.connected:
            self.update_connection_state(False, self.connection_status.text())

    def prompt_demo_range(self):
        from PySide6.QtWidgets import (
            QComboBox,
            QDialog,
            QDialogButtonBox,
            QDoubleSpinBox,
            QFormLayout,
            QLabel,
            QVBoxLayout,
        )

        dialog = QDialog(self.window)
        dialog.setWindowTitle("Start Demo Mode")
        dialog.setMinimumWidth(420)
        layout = QVBoxLayout(dialog)
        intro = QLabel("Choose the simulated RF range before connecting to Demo Mode.")
        intro.setWordWrap(True)
        form = QFormLayout()

        preset_combo = QComboBox()
        for label, low, high in DEMO_RANGE_PRESETS:
            preset_combo.addItem(f"{label} ({low:.3f}–{high:.3f} MHz)", (low, high))
        preset_combo.addItem("Custom range", None)

        low_spin = QDoubleSpinBox()
        low_spin.setRange(100.0, 1200.0)
        low_spin.setDecimals(3)
        low_spin.setSingleStep(1.0)
        low_spin.setSuffix(" MHz")
        high_spin = QDoubleSpinBox()
        high_spin.setRange(100.0, 1200.0)
        high_spin.setDecimals(3)
        high_spin.setSingleStep(1.0)
        high_spin.setSuffix(" MHz")
        low_spin.setValue(float(self.settings.get_float("demo_low_mhz", 470.0)))
        high_spin.setValue(float(self.settings.get_float("demo_high_mhz", 608.0)))

        def apply_preset(index):
            data = preset_combo.itemData(index)
            if data:
                low, high = data
                low_spin.setValue(low)
                high_spin.setValue(high)

        preset_combo.currentIndexChanged.connect(apply_preset)
        if not self.settings.get("demo_low_mhz"):
            apply_preset(0)

        form.addRow("Preset", preset_combo)
        form.addRow("Low frequency", low_spin)
        form.addRow("High frequency", high_spin)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(intro)
        layout.addLayout(form)
        layout.addWidget(buttons)
        dialog.setStyleSheet(self.stylesheet())

        if dialog.exec() != QDialog.Accepted:
            return None
        low = float(low_spin.value())
        high = float(high_spin.value())
        if high <= low:
            self.show_error("Demo Mode high frequency must be greater than low frequency.")
            return None
        if high - low < 1.0:
            self.show_error("Demo Mode range must be at least 1 MHz wide.")
            return None
        self.settings.set("demo_low_mhz", low)
        self.settings.set("demo_high_mhz", high)
        return low, high

    def start_demo_mode(self):
        selected_range = self.prompt_demo_range()
        if selected_range is None:
            self.log("Demo Mode canceled")
            return
        self.demo_low_mhz, self.demo_high_mhz = selected_range
        self.demo_connect_pending = True
        self.force_disconnected_actions = False
        self.selected_port = "Demo Mode"
        self.device_info_label.setText(
            f"Device: Demo Mode\nRange: {self.demo_low_mhz:.3f}–{self.demo_high_mhz:.3f} MHz"
        )
        self.show_device_notice("Preparing simulated RF scan…")
        self.update_connection_state(False, "Connecting…")
        self.disconnect_button.setText("Disconnect Demo")
        self.log(
            f"Connecting to Demo Mode ({self.demo_low_mhz:.3f}–{self.demo_high_mhz:.3f} MHz)"
        )
        self.QTimer.singleShot(DEMO_CONNECT_HOLD_MS, self.finish_demo_connect)

    def finish_demo_connect(self):
        if not self.demo_connect_pending or self.shutting_down:
            return
        self.demo_connect_pending = False
        self.demo_mode = True
        self.connected = True
        self.selected_port = "Demo Mode"
        low = float(self.demo_low_mhz)
        high = float(self.demo_high_mhz)
        points = 450
        step = (high - low) / (points - 1)
        self.freqs_mhz = [low + (index * step) for index in range(points)]
        self.live_freqs_mhz = self.freqs_mhz.copy()
        self.latest_dbm = []
        self.display_dbm = []
        self.demo_phase = 0.0
        self.reset_peaks()
        self.plot.setXRange(min(self.freqs_mhz), max(self.freqs_mhz), padding=0)
        self.lock_plot_axes(preserve_x=True)
        self.update_frequency_range_labels()
        self.cursor_line.setPos(self.freqs_mhz[0])
        self.device_info_label.setText(f"Device: Demo Mode\nRange: {low:.3f}–{high:.3f} MHz")
        self.show_device_notice("Demo Mode is visual only. No CSV files are written.")
        self.update_connection_state(True, "Connected")
        self.disconnect_button.setText("Disconnect Demo")
        self.render_mic_markers()
        self.log("Demo Mode connected; CSV export disabled")

        self.demo_timer = self.QTimer(self.window)
        self.demo_timer.timeout.connect(self.generate_demo_scan)
        self.demo_timer.start(int(self.refresh_seconds * 1000))
        self.generate_demo_scan()

    def stop_demo_mode(self):
        self.demo_connect_pending = False
        if self.demo_timer is not None:
            self.demo_timer.stop()
            self.demo_timer.deleteLater()
            self.demo_timer = None
        self.demo_mode = False
        self.connected = False
        self.selected_port = None
        self.latest_dbm = []
        self.display_dbm = []
        self.live_freqs_mhz = []
        self.freqs_mhz = []
        self.live_curve.setData([], [])
        self.peak_curve.setData([], [])
        self.update_frequency_range_labels([])
        self.clear_device_notice()
        self.update_top_frequencies([])
        self.render_mic_markers()
        self.update_connection_state(False)
        self.disconnect_button.setText("Disconnect")
        self.log("Demo Mode stopped")

    def generate_demo_scan(self):
        if not self.demo_mode or not self.freqs_mhz:
            return

        self.demo_phase += 0.28
        low = min(self.freqs_mhz)
        high = max(self.freqs_mhz)
        span = max(1.0, high - low)
        shure_like_centers = [482.125, 506.500, 537.875, 584.250, 604.200]
        peaks = []
        for fallback_ratio, center in zip((0.18, 0.42, 0.68), shure_like_centers):
            if low <= center <= high:
                peaks.append((center, random.choice((-48, -51, -56)), max(0.12, span * 0.002)))
            else:
                peaks.append((low + span * fallback_ratio, random.choice((-48, -51, -56)), max(0.12, span * 0.002)))
        transient_spikes = [
            (
                random.uniform(low + span * 0.02, high - span * 0.02),
                random.uniform(-74.0, -60.0),
                random.uniform(max(0.035, span * 0.0004), max(0.09, span * 0.001)),
            )
            for _ in range(5)
        ]
        dbm = []
        for index, freq in enumerate(self.freqs_mhz):
            floor = (
                -94
                + 2.8 * math.sin((freq * 0.11) + self.demo_phase)
                + 1.4 * math.sin((freq * 0.53) - (self.demo_phase * 0.7))
                + 0.9 * math.sin((index * 0.37) + (self.demo_phase * 1.8))
            )
            level = floor + random.gauss(0, 2.4) + random.uniform(-1.2, 1.2)
            for center, peak_level, width in peaks:
                drift = 0.055 * math.sin(self.demo_phase + center)
                jitter = random.uniform(-1.4, 1.0)
                strength = math.exp(-((freq - center - drift) ** 2) / (2 * width * width))
                level = max(level, (peak_level + jitter) * strength + floor * (1 - strength))
            for center, spike_level, width in transient_spikes:
                strength = math.exp(-((freq - center) ** 2) / (2 * width * width))
                level = max(level, spike_level * strength + floor * (1 - strength))
            if random.random() < 0.018:
                level = max(level, random.uniform(-82.0, -68.0))
            dbm.append(level)

        self.latest_dbm = dbm
        self.freqs_mhz = self.live_freqs_mhz
        if not self.frozen:
            self.render_scan(dbm)
        self.update_status()

    def on_connected(self, port, version, freqs_mhz):
        self.auto_connect_in_progress = False
        self.force_disconnected_actions = False
        self.pending_disconnect_status = None
        self.scan_mismatch_count = 0
        self.scan_error_count = 0
        self.connected = True
        self.selected_port = port
        self.device_name = version or "tinySA"
        self.freqs_mhz = freqs_mhz
        self.live_freqs_mhz = freqs_mhz.copy()
        self.latest_dbm = []
        self.display_dbm = []
        self.reset_peaks()
        self.plot.setXRange(min(freqs_mhz), max(freqs_mhz), padding=0)
        self.lock_plot_axes(preserve_x=True)
        self.update_frequency_range_labels()
        self.cursor_line.setPos(freqs_mhz[0])
        self.render_mic_markers()
        self.device_info_label.setText(
            f"Device: {version or 'tinySA'}\n"
            f"Range: {min(freqs_mhz):.3f}–{max(freqs_mhz):.3f} MHz"
        )
        self.clear_device_notice()
        self.update_connection_state(True, "Connected")
        self.disconnect_button.setText("Disconnect tinySA")
        self.log(f"Frequency range: {min(freqs_mhz):.3f}–{max(freqs_mhz):.3f} MHz")

    def on_disconnected(self):
        was_connected = self.connected
        status_text = self.pending_disconnect_status
        self.pending_disconnect_status = None
        self.connected = False
        self.scan_mismatch_count = 0
        self.update_connection_state(False, status_text)
        self.render_mic_markers()
        if was_connected:
            self.log("Disconnected")

    def on_worker_reconnecting(self, message):
        self.show_device_notice(message)
        self.update_connection_state(True, "Reconnecting…")

    def is_device_unavailable_error(self, message):
        lowered = str(message).lower()
        return any(marker in lowered for marker in DEVICE_UNAVAILABLE_MARKERS)

    def mark_device_unavailable(self, status, notice, log_message=None):
        self.auto_connect_in_progress = False
        self.force_disconnected_actions = True
        self.pending_disconnect_status = status
        self.show_device_notice(notice)
        self.update_connection_state(False, status)
        if log_message:
            self.log(log_message)
        self.disconnect_device()

    def on_worker_error(self, message):
        if self.shutting_down:
            return

        message_text = str(message)
        lowered = message_text.lower()

        if "could not reconnect" in lowered:
            self.log(message_text)
            self.mark_device_unavailable(
                "Reconnect failed",
                "tinySA stopped responding and RF Bridge could not reconnect. Power-cycle or restart the tinySA, then restart RF Bridge.",
            )
            return

        if self.is_device_unavailable_error(message_text):
            self.log("tinySA disconnected or stopped responding")
            self.mark_device_unavailable(
                "Disconnected — tinySA unavailable",
                "tinySA disconnected or stopped responding. Reconnect/power-cycle it, then connect again.",
            )
            return

        self.log(message_text)

        transient_empty_read = (
            "returned no data" in lowered
            or "no frequency points" in lowered
            or "frequency range" in lowered
        )

        if transient_empty_read:
            self.scan_error_count += 1
            self.mark_device_unavailable(
                "Disconnected — tinySA not ready",
                "tinySA is not returning data. Reboot/power-cycle the tinySA, then reconnect.",
                "tinySA did not return data; disconnected for retry/reconnect",
            )
            # Do not show a modal startup warning for this recoverable case. The
            # app should stay usable for capture overlays and manual reconnect.
            return

        # Auto-connect should never block app startup with a modal error.
        # Manual non-transient errors still show the warning so troubleshooting is obvious.
        if self.auto_connect_in_progress:
            self.mark_device_unavailable(
                "Disconnected — tinySA not ready",
                "tinySA is not ready. Reconnect or power-cycle it, then connect again.",
            )
            return
        self.show_error(message_text)

    def update_connection_state(self, connected, text=None):
        if connected:
            self.force_disconnected_actions = False
        self.connected = connected
        status_text = text or ("Connected" if connected else "Disconnected")
        is_connecting = "connecting" in status_text.lower() or "reconnecting" in status_text.lower()
        if is_connecting:
            status_color = "#d0a000"
        elif connected:
            status_color = self.theme["connected"]
        else:
            status_color = self.theme["disconnected"]
        self.status_dot.setStyleSheet(f"color: {status_color};")
        self.connection_status.setText(status_text)
        self.connection_status.setStyleSheet(
            f"background: {self.theme['hover_bg']}; color: {status_color}; "
            f"border: 1px solid {status_color}; border-radius: 12px; "
            "padding: 3px 10px; font-weight: bold; font-size: 14px;"
        )
        self.sidebar_connection_label.setText(status_text)
        device_name = "Demo Mode" if (self.demo_mode or self.demo_connect_pending) else (self.device_name if connected else "—")
        self.sidebar_device_label.setText(f"Device: {device_name}")
        show_disconnect = (connected or self.worker is not None or self.demo_connect_pending) and not self.force_disconnected_actions
        controls_busy = connected or self.worker is not None or self.demo_connect_pending
        self.connect_button.setVisible(not show_disconnect)
        self.refresh_ports_button.setVisible(not show_disconnect)
        self.disconnect_button.setVisible(show_disconnect)
        self.connect_button.setEnabled(not controls_busy)
        self.disconnect_button.setEnabled(show_disconnect)
        self.refresh_ports_button.setEnabled(not controls_busy)
        self.port_combo.setEnabled(not controls_busy)
        if not connected and not self.demo_connect_pending:
            self.device_info_label.setText("Device: —\nRange: —")
            self.disconnect_button.setText("Disconnect")
            if self.worker is None and not self.demo_mode:
                self.update_frequency_range_labels([])
                self.update_frequency_bounds([])
                self.render_mic_markers()
        self.update_status()

    def update_frequency_range_labels(self, freqs_mhz=None):
        if freqs_mhz is None:
            freqs_mhz = self.freqs_mhz

        if not freqs_mhz:
            self.low_freq_label.setVisible(False)
            self.high_freq_label.setVisible(False)
            return

        low_freq = min(freqs_mhz)
        high_freq = max(freqs_mhz)
        label_y = RF_Y_MIN + 4
        self.low_freq_label.setText(f"Low {low_freq:.3f} MHz")
        self.high_freq_label.setText(f"High {high_freq:.3f} MHz")
        self.low_freq_label.setColor(self.theme["axis_text"])
        self.high_freq_label.setColor(self.theme["axis_text"])
        self.low_freq_label.setPos(low_freq, label_y)
        self.high_freq_label.setPos(high_freq, label_y)
        self.low_freq_label.setVisible(True)
        self.high_freq_label.setVisible(True)

    def show_device_notice(self, message):
        self.device_notice_label.setText(message)
        self.device_notice_label.setVisible(True)

    def clear_device_notice(self):
        self.device_notice_label.setText("")
        self.device_notice_label.setVisible(False)

    def show_error(self, message):
        if self.shutting_down:
            return
        self.QMessageBox.warning(self.window, "RF Bridge", message)

    def nearest_index(self, freq):
        if not self.freqs_mhz:
            return 0
        idx = bisect.bisect_left(self.freqs_mhz, freq)
        if idx <= 0:
            return 0
        if idx >= len(self.freqs_mhz):
            return len(self.freqs_mhz) - 1
        before = idx - 1
        after = idx
        return before if abs(self.freqs_mhz[before] - freq) <= abs(self.freqs_mhz[after] - freq) else after

    def set_refresh_interval(self, seconds):
        self.refresh_seconds = seconds
        self.settings.set("refresh_seconds", seconds)
        self.refresh_button.setText(f"  {format_seconds(seconds)}s")
        if self.demo_timer is not None:
            self.demo_timer.start(int(seconds * 1000))
        if self.worker is not None:
            self.QMetaObject.invokeMethod(
                self.worker,
                "set_refresh_seconds",
                self.Qt.QueuedConnection,
                self.Q_ARG(float, float(seconds)),
            )
        self.log(f"Refresh set to {format_seconds(seconds)}s")
        self.update_status()

    def toggle_refresh(self):
        self.refresh_index = min(
            range(len(REFRESH_MODES)),
            key=lambda index: abs(REFRESH_MODES[index] - self.refresh_seconds),
        )
        self.refresh_index = (self.refresh_index + 1) % len(REFRESH_MODES)
        self.set_refresh_interval(REFRESH_MODES[self.refresh_index])

    def show_refresh_menu(self, position):
        from PySide6.QtWidgets import QInputDialog

        menu = self.QMenu(self.window)
        for value in REFRESH_MODES:
            label = f"{format_seconds(value)} seconds"
            action = menu.addAction(label)
            action.setCheckable(True)
            action.setChecked(abs(value - self.refresh_seconds) < 0.001)
            action.triggered.connect(lambda _checked=False, seconds=value: self.set_refresh_interval(seconds))
        menu.addSeparator()
        custom_action = menu.addAction("Custom…")

        def choose_custom():
            value, ok = QInputDialog.getDouble(
                self.window,
                "Custom Refresh",
                "Refresh interval in seconds:",
                float(self.refresh_seconds),
                0.1,
                3600.0,
                1,
            )
            if ok:
                self.set_refresh_interval(float(value))

        custom_action.triggered.connect(choose_custom)
        menu.exec(self.refresh_button.mapToGlobal(position))

    def toggle_freeze(self):
        self.frozen = not self.frozen
        self.freeze_button.setText("  Resume" if self.frozen else "  Freeze")
        self.log("Trace frozen" if self.frozen else "Trace resumed")
        if not self.frozen and self.latest_dbm and self.freqs_mhz:
            self.render_scan(self.latest_dbm)

    def toggle_peak(self):
        self.peak_mode_index = (self.peak_mode_index + 1) % len(PEAK_MODES)
        self.set_peak_mode(self.peak_mode_index)

    def show_peak_menu(self, position):
        menu = self.QMenu(self.window)
        for index, (label, _window_seconds) in enumerate(PEAK_MODES):
            action = menu.addAction(label)
            action.setCheckable(True)
            action.setChecked(index == self.peak_mode_index)
            action.triggered.connect(lambda _checked=False, i=index: self.set_peak_mode(i))
        menu.exec(self.peak_button.mapToGlobal(position))

    def set_peak_mode(self, index):
        self.peak_mode_index = index % len(PEAK_MODES)
        self.settings.set("peak_mode_index", self.peak_mode_index)
        label, window_seconds = PEAK_MODES[self.peak_mode_index]
        self.peak_button.setText(f"  Peak {label}")
        if label == "OFF":
            self.peak_enabled = False
            self.peak_hold = None
            self.peak_history = deque()
            self.peak_curve.setData([], [])
        else:
            self.peak_enabled = True
            if self.latest_dbm:
                now = time.time()
                self.peak_history.append((now, self.latest_dbm.copy()))
                self.peak_hold = self.latest_dbm.copy()
                self.peak_curve.setData(self.freqs_mhz, self.peak_hold)
        self.log(f"Peak mode: {label}")

    def reset_peaks(self):
        self.peak_enabled = False
        self.peak_mode_index = 0
        self.peak_hold = None
        self.peak_history = deque()
        self.peak_button.setText("  Peak OFF")
        self.peak_curve.setData([], [])
        self.update_hover_label(None)

    def on_scan_ready(self, dbm):
        self.scan_error_count = 0
        live_freqs = self.live_freqs_mhz or self.freqs_mhz
        if not live_freqs:
            return
        if len(dbm) != len(live_freqs):
            self.scan_mismatch_count += 1
            if self.scan_mismatch_count == 1:
                self.log(
                    "tinySA scan point count changed; waiting for a clean scan "
                    f"({len(live_freqs)} freqs, {len(dbm)} levels)"
                )
            if self.scan_mismatch_count >= MAX_CONSECUTIVE_SCAN_MISMATCHES:
                self.mark_device_unavailable(
                    "Disconnected — tinySA data changed",
                    "tinySA scan data no longer matches the frequency range. Connect again to refresh the range.",
                    "tinySA data stayed out of sync; disconnected for reconnect",
                )
            return
        self.scan_mismatch_count = 0
        self.latest_dbm = dbm
        if self.capture_mode:
            self.return_live_button.setEnabled(True)
        else:
            self.freqs_mhz = live_freqs
            self.last_cursor_index = None
            if not self.frozen:
                self.render_scan(dbm)
        now = time.time()
        if self.auto_trace_enabled and not self.capture_mode:
            if not self.last_auto_trace_time:
                self.last_auto_trace_time = now
            elif now - self.last_auto_trace_time >= self.auto_trace_minutes * 60:
                self.add_auto_trace_overlay(live_freqs, dbm, now=now)
        if now - self.last_save_time >= SCAN_INTERVAL_SECONDS:
            filename, latest_filename = save_wwb_csv(
                self.output_dir,
                self.gig_slug,
                live_freqs,
                dbm,
                self.device_name,
                self.filename_time_format,
            )
            self.last_save_time = now
            self.log(f"Saved scan: {os.path.basename(filename)}")
        self.update_status(now)

    def render_scan(self, dbm):
        self.display_dbm = dbm
        if self.peak_enabled:
            now = time.time()
            label, window_seconds = PEAK_MODES[self.peak_mode_index]
            self.peak_history.append((now, dbm.copy()))
            if window_seconds == "latch":
                if self.peak_hold is None:
                    self.peak_hold = dbm.copy()
                else:
                    self.peak_hold = [max(old, new) for old, new in zip(self.peak_hold, dbm)]
            else:
                cutoff = now - window_seconds
                while self.peak_history and self.peak_history[0][0] < cutoff:
                    self.peak_history.popleft()
                if self.peak_history:
                    samples = (sample[1] for sample in self.peak_history)
                    self.peak_hold = [max(values) for values in zip(*samples)]
            if self.peak_hold:
                self.peak_curve.setData(self.freqs_mhz, self.peak_hold)
        self.live_curve.setData(self.freqs_mhz, dbm)
        self.update_frequency_range_labels()
        self.update_top_frequencies(dbm)
        self.lock_plot_axes(preserve_x=True)
        self.plot.setTitle(f"RF Bridge - {self.gig_slug} - {time_12h()}", color=self.theme["text"], size="16pt")

    def update_top_frequencies(self, dbm):
        if not dbm:
            self.summary_label.setText("RF SUMMARY\n──────────────────────\n\nConnect to tinySA to begin.")
            for marker in self.top_markers:
                self.plot.removeItem(marker)
            self.top_markers = []
            return

        median_floor = sorted(dbm)[len(dbm) // 2]
        strongest = heapq.nlargest(8, zip(self.freqs_mhz, dbm), key=lambda pair: pair[1])
        text = "RF SUMMARY\n──────────────────────\n\n"
        text += "Median Floor\n"
        text += f"{median_floor:7.2f} dBm\n\n"
        text += "TOP 8 RF HITS\n──────────────────────\n"
        for i, (freq, level) in enumerate(strongest, start=1):
            display_freq = snap_display_frequency(freq)
            text += f"{i}. {display_freq:9.3f} MHz  {level:7.2f} dBm\n"
        self.summary_label.setText(text)
        while len(self.top_markers) < len(strongest):
            marker = self.pg.InfiniteLine(
                angle=90,
                pen=self.pg.mkPen(self.theme["marker"], width=1, style=self.Qt.DotLine),
            )
            marker.setZValue(-10)
            self.plot.addItem(marker, ignoreBounds=True)
            self.top_markers.append(marker)
        for marker, (freq, _level) in zip(self.top_markers, strongest):
            marker.setPen(self.pg.mkPen(self.theme["marker"], width=1, style=self.Qt.DotLine))
            marker.setPos(freq)
            marker.setVisible(True)
        for marker in self.top_markers[len(strongest):]:
            marker.setVisible(False)

    def update_hover_label(self, idx):
        source = self.display_dbm or self.latest_dbm
        if idx is None or not source or not self.freqs_mhz:
            self.hover_label.setText("Hover graph for readout.")
            return
        nearest_freq = self.freqs_mhz[idx]
        nearest_level = source[idx]
        display_freq = snap_display_frequency(nearest_freq)
        if self.capture_mode and self.loaded_capture:
            mode_text = "\nMode: Capture"
        else:
            mode_text = "\nMode: Frozen" if self.frozen else ""
        if self.peak_hold:
            nearest_peak = self.peak_hold[idx]
            self.hover_label.setText(
                f"{display_freq:.3f} MHz\n"
                f"Live: {nearest_level:.2f} dBm\n"
                f"Peak: {nearest_peak:.2f} dBm{mode_text}"
            )
        else:
            self.hover_label.setText(
                f"{display_freq:.3f} MHz\n"
                f"Live: {nearest_level:.2f} dBm{mode_text}"
            )

    def on_mouse_move(self, scene_pos):
        if not self.freqs_mhz or not (self.display_dbm or self.latest_dbm):
            return
        plot_item = self.plot.getPlotItem()
        view_box = plot_item.vb
        if not view_box.sceneBoundingRect().contains(scene_pos):
            self.cursor_line.setVisible(False)
            self.update_hover_label(None)
            return
        mouse_point = view_box.mapSceneToView(scene_pos)
        idx = self.nearest_index(mouse_point.x())
        if idx == self.last_cursor_index:
            return
        self.last_cursor_index = idx
        nearest_freq = self.freqs_mhz[idx]
        self.cursor_line.setPos(nearest_freq)
        self.cursor_line.setVisible(True)
        self.update_hover_label(idx)

    def update_status(self, now=None):
        if now is None:
            now = time.time()
        if self.last_save_time:
            next_save = max(0, SCAN_INTERVAL_SECONDS - int(now - self.last_save_time))
        else:
            next_save = 0
        minutes = next_save // 60
        seconds = next_save % 60
        if self.capture_mode and self.loaded_capture:
            freeze_label = "Capture"
        elif self.demo_connect_pending:
            freeze_label = "Demo Connecting"
        elif self.demo_mode:
            freeze_label = "Demo"
        else:
            freeze_label = "Frozen" if self.frozen else "Live"
        device_label = self.selected_port or "not connected"
        overlay_count = sum(1 for capture in self.capture_overlays if capture.get("visible", True))
        auto_label = "on" if self.auto_trace_enabled else "off"
        if self.demo_mode or self.demo_connect_pending:
            self.status_label.setText(
                f"Mode: {freeze_label}   |   CSV: disabled   |   "
                f"Refresh: {format_seconds(self.refresh_seconds)}s   |   Overlays: {overlay_count}   |   Auto: {auto_label}"
            )
            return
        folder_label = os.path.basename(os.path.normpath(self.output_dir)) or self.output_dir
        latest_label = "latest_scan.csv" if self.last_save_time else "waiting"
        self.status_label.setText(
            f"Folder: {folder_label}   |   Latest: {latest_label}   |   "
            f"Next: {minutes}:{seconds:02d}   |   Refresh: {format_seconds(self.refresh_seconds)}s   |   "
            f"Mode: {freeze_label}   |   Overlays: {overlay_count}   |   Auto: {auto_label}"
        )

    def handle_close_event(self, event):
        self.shutdown()
        event.accept()

    def shutdown(self):
        if self.shutdown_started:
            return

        self.shutdown_started = True
        self.shutting_down = True

        try:
            self.settings.set("window_geometry", self.window.saveGeometry())
        except Exception:
            pass

        worker = self.worker
        worker_thread = self.worker_thread
        auto_detect_thread = self.auto_detect_thread

        if worker is not None:
            try:
                connection_type = self.Qt.BlockingQueuedConnection
                if worker.thread() == self.app.thread():
                    connection_type = self.Qt.DirectConnection
                self.QMetaObject.invokeMethod(
                    worker,
                    "stop",
                    connection_type,
                )
            except Exception:
                try:
                    self.QMetaObject.invokeMethod(
                        worker,
                        "stop",
                        self.Qt.QueuedConnection,
                    )
                except Exception:
                    pass

        if worker_thread is not None:
            try:
                worker_thread.quit()
                if not worker_thread.wait(3000):
                    self.log("Worker thread did not exit cleanly within 3 seconds; forcing termination")
                    worker_thread.terminate()
                    worker_thread.wait(1000)
            except RuntimeError:
                pass

        if auto_detect_thread is not None:
            try:
                auto_detect_thread.quit()
                if not auto_detect_thread.wait(1000):
                    auto_detect_thread.terminate()
                    auto_detect_thread.wait(500)
            except RuntimeError:
                pass

        self.worker = None
        self.worker_thread = None
        self.auto_detect_worker = None
        self.auto_detect_thread = None
        self.connected = False

    def run(self):
        self.window.show()
        exit_code = self.app.exec()
        self.shutdown()
        return exit_code


def run_ui(output_dir, gig_slug, ui_update_seconds=UI_UPDATE_SECONDS, selected_port=None, debug_serial=False):
    window = RFBridgeWindow(
        output_dir=output_dir,
        gig_slug=gig_slug,
        ui_update_seconds=ui_update_seconds,
        selected_port=selected_port,
        debug_serial=debug_serial,
    )
    return window.run()

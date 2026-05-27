"""PySide6 / pyqtgraph RF Bridge v1.9.5.2 UI."""

import bisect
import json
import os
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

# Fixed RF display range. Keep the graph from re-scaling when the tinySA
# connects, when live data arrives, or when guide/marker items are refreshed.
RF_Y_MIN = -110
RF_Y_MAX = -20
RF_Y_RANGE = RF_Y_MAX - RF_Y_MIN


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
            error = Signal(str)
            log = Signal(str)

        return UiBridge()


def format_seconds(seconds):
    if float(seconds).is_integer():
        return str(int(seconds))
    return str(seconds)


class RFBridgeWindow:
    def __init__(self, output_dir, gig_slug, ui_update_seconds=UI_UPDATE_SECONDS, selected_port=None, debug_serial=False):
        from PySide6.QtCore import Qt, QThread, Signal, QMetaObject, Q_ARG, QTimer, QSize
        from PySide6.QtGui import QAction, QPixmap
        from PySide6.QtWidgets import (
            QApplication,
            QCheckBox,
            QComboBox,
            QFrame,
            QGridLayout,
            QHBoxLayout,
            QLabel,
            QMainWindow,
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
        self.QTimer = QTimer
        self.QAction = QAction
        self.pg = pg

        self.output_dir = output_dir
        self.gig_slug = gig_slug
        self.selected_port = selected_port
        self.debug_serial = debug_serial
        self.freqs_mhz = []
        self.latest_dbm = []
        self.display_dbm = []
        self.last_save_time = 0
        self.last_cursor_index = None
        self.peak_mode_index = 0
        self.peak_enabled = False
        self.peak_hold = None
        self.peak_history = []
        self.top_markers = []
        self.mic_markers = []
        self.mic_marker_items = []
        self.frozen = False
        self.loaded_capture = None
        self.capture_mode = False
        self.capture_overlays = []
        self.capture_overlay_items = []
        self.capture_overlay_actions = []
        self.overlay_checkbox_widgets = []
        self.overlay_color_index = 0
        self.scan_error_count = 0
        self.auto_connect_in_progress = False
        self.shutting_down = False
        self.shutdown_started = False
        self.live_freqs_mhz = []
        self.connected = False
        self.worker_thread = None
        self.worker = None
        self.port_map = {}
        self.settings = AppSettings()
        self.appearance = self.settings.get_appearance()
        self.theme_name = self.resolve_theme_name(self.appearance)
        self.theme = THEMES[self.theme_name]
        self.ui_bridge = UiBridgeFactory.create()
        self.ui_bridge.connected.connect(self.on_connected)
        self.ui_bridge.scan_ready.connect(self.on_scan_ready)
        self.ui_bridge.error.connect(self.on_worker_error)
        self.ui_bridge.log.connect(self.log)
        self.ui_bridge.disconnected.connect(self.on_disconnected)

        saved_refresh = self.settings.get_float("refresh_seconds", ui_update_seconds)
        self.refresh_index = min(
            range(len(REFRESH_MODES)),
            key=lambda index: abs(REFRESH_MODES[index] - saved_refresh),
        )
        self.refresh_seconds = REFRESH_MODES[self.refresh_index]
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

        saved_geometry = self.settings.get_bytes("window_geometry")
        if saved_geometry:
            self.window.restoreGeometry(saved_geometry)

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
            button.setMinimumHeight(38)
            button.setFlat(True)
            sidebar_layout.addWidget(button)

        self.rf_scan_button.setEnabled(False)
        sidebar_layout.addStretch(1)

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
        self.port_combo = QComboBox()
        self.refresh_ports_button = QPushButton("Refresh Ports")
        self.connect_button = QPushButton("Connect")
        self.disconnect_button = QPushButton("Disconnect")
        self.disconnect_button.setEnabled(False)
        self.disconnect_button.setVisible(False)
        self.device_info_label = QLabel("Device: —\nRange: —")
        self.device_info_label.setObjectName("deviceInfoLabel")
        self.device_notice_label = QLabel("")
        self.device_notice_label.setObjectName("deviceNoticeLabel")
        self.device_notice_label.setWordWrap(True)
        self.device_notice_label.setVisible(False)

        self.port_combo.setMinimumWidth(220)
        self.port_combo.setMaximumWidth(330)
        self.refresh_ports_button.setText("Refresh")
        for _btn in (self.refresh_ports_button, self.connect_button, self.disconnect_button):
            _btn.setMinimumHeight(26)
            _btn.setMaximumHeight(30)
        self.disconnect_button.setEnabled(False)

        connection_layout.addWidget(self.status_dot, 0, 0)
        connection_layout.addWidget(self.connection_status, 0, 1, 1, 3)
        connection_layout.addWidget(self.port_combo, 1, 0, 1, 4)
        connection_layout.addWidget(self.connect_button, 2, 0, 1, 2)
        connection_layout.addWidget(self.disconnect_button, 2, 0, 1, 4)
        connection_layout.addWidget(self.refresh_ports_button, 2, 2, 1, 2)
        connection_layout.addWidget(self.device_info_label, 3, 0, 1, 4)
        connection_layout.addWidget(self.device_notice_label, 4, 0, 1, 4)
        connection_layout.setColumnStretch(1, 1)
        connection_panel.setFixedWidth(330)
        connection_panel.setMinimumHeight(160)
        connection_panel.setMaximumHeight(195)

        self.overlay_panel = QFrame()
        self.overlay_panel.setObjectName("overlayPanel")
        self.overlay_panel.setMinimumHeight(160)
        self.overlay_panel.setMaximumHeight(175)
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
        self.overlay_controls_row = QHBoxLayout()
        self.overlay_controls_row.setSpacing(10)
        self.overlay_empty_label = QLabel("No overlays loaded")
        self.overlay_empty_label.setObjectName("overlayEmptyLabel")
        self.overlay_empty_label.setAlignment(self.Qt.AlignCenter)
        self.overlay_empty_hint = QLabel("Click “Open Overlay(s)…” to load one or more capture files (CSV).")
        self.overlay_empty_hint.setObjectName("overlayEmptyHint")
        self.overlay_empty_hint.setAlignment(self.Qt.AlignCenter)
        self.overlay_controls_row.addStretch(1)
        self.overlay_controls_row.addWidget(self.overlay_empty_label)
        self.overlay_controls_row.addStretch(1)
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
        self.plot = pg.PlotWidget()
        self.plot.setBackground(self.theme["plot_bg"])
        self.plot.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.plot.showGrid(x=True, y=True, alpha=0.25)
        self.plot.setLabel("bottom", "Frequency", units="MHz")
        self.plot.setLabel("left", "dBm")
        self.plot.setTitle(f"RF Bridge - {self.gig_slug}", color=self.theme["text"], size="16pt")
        self.lock_plot_axes()

        axis_pen = pg.mkPen(self.theme["axis"])
        self.plot.getAxis("bottom").setPen(axis_pen)
        self.plot.getAxis("left").setPen(axis_pen)
        self.plot.getAxis("bottom").setTextPen(self.theme["axis_text"])
        self.plot.getAxis("left").setTextPen(self.theme["axis_text"])

        self.live_curve = self.plot.plot([], [], pen=pg.mkPen("#00ff99", width=2), name="Live")
        self.peak_curve = self.plot.plot([], [], pen=pg.mkPen("#ff3333", width=1.5), name="Peak Hold")
        self.threshold_85 = pg.InfiniteLine(pos=-85, angle=0, pen=pg.mkPen("#ffaa00", width=1, style=self.Qt.DashLine))
        self.threshold_60 = pg.InfiniteLine(pos=-60, angle=0, pen=pg.mkPen("#ff00aa", width=1, style=self.Qt.DashLine))
        self.plot.addItem(self.threshold_85, ignoreBounds=True)
        self.plot.addItem(self.threshold_60, ignoreBounds=True)
        self.cursor_line = pg.InfiniteLine(pos=0, angle=90, pen=pg.mkPen("#00ff99", width=1))
        self.cursor_line.setVisible(False)
        self.plot.addItem(self.cursor_line, ignoreBounds=True)

        side_panel = QFrame()
        side_panel.setObjectName("sidePanel")
        side_panel.setFixedWidth(330)
        side_layout = QVBoxLayout(side_panel)
        side_layout.setContentsMargins(12, 12, 12, 12)
        side_layout.setSpacing(12)

        self.summary_label = QLabel("RF SUMMARY\n──────────────────────\n\nConnect to tinySA to begin.")
        self.summary_label.setObjectName("summaryLabel")
        self.summary_label.setAlignment(self.Qt.AlignTop | self.Qt.AlignLeft)
        self.summary_label.setTextInteractionFlags(self.Qt.TextSelectableByMouse)
        self.hover_label = QLabel("Hover over the graph for live readout.")
        self.hover_label.setObjectName("hoverLabel")
        self.hover_label.setAlignment(self.Qt.AlignTop | self.Qt.AlignLeft)
        self.hover_label.setTextInteractionFlags(self.Qt.TextSelectableByMouse)
        # Keep the hover readout from asking Qt's layout system for more height
        # as the cursor moves. Without this, vertical mouse movement over the
        # graph can make the main window grow unexpectedly on macOS.
        self.hover_label.setMinimumHeight(82)
        self.hover_label.setMaximumHeight(96)

        self.peak_button = QPushButton("Peak: OFF")
        self.reset_button = QPushButton("Reset Peaks")
        self.refresh_button = QPushButton(f"Refresh: {format_seconds(self.refresh_seconds)}s")
        self.freeze_button = QPushButton("Freeze: OFF")
        self.return_live_button = QPushButton("Return to Live")
        self.return_live_button.setEnabled(False)
        for button in (self.peak_button, self.reset_button, self.refresh_button, self.freeze_button, self.return_live_button):
            button.setMinimumHeight(42)

        side_layout.addWidget(self.summary_label, stretch=1)
        side_layout.addWidget(self.hover_label)
        side_layout.addWidget(self.peak_button)
        side_layout.addWidget(self.reset_button)
        side_layout.addWidget(self.refresh_button)
        side_layout.addWidget(self.freeze_button)
        side_layout.addWidget(self.return_live_button)

        content_layout.addWidget(self.plot, stretch=1)
        content_layout.addWidget(side_panel)

        self.log_box = QTextEdit()
        self.log_box.setObjectName("logBox")
        self.log_box.setReadOnly(True)
        self.log_box.setMaximumHeight(96)
        self.status_label = QLabel("")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setMinimumHeight(38)
        self.status_label.setTextInteractionFlags(self.Qt.TextSelectableByMouse)

        root_layout.addLayout(top_layout)
        root_layout.addLayout(content_layout, stretch=2)
        root_layout.addWidget(self.log_box)
        root_layout.addWidget(self.status_label)
        self.window.setCentralWidget(root)

        self.create_menus()
        self.apply_theme()

        self.refresh_ports_button.clicked.connect(self.populate_ports)
        self.connect_button.clicked.connect(self.connect_device)
        self.disconnect_button.clicked.connect(self.disconnect_device)
        self.peak_button.clicked.connect(self.toggle_peak)
        self.reset_button.clicked.connect(self.reset_peaks)
        self.refresh_button.clicked.connect(self.toggle_refresh)
        self.freeze_button.clicked.connect(self.toggle_freeze)
        self.return_live_button.clicked.connect(self.return_to_live)
        self.open_overlay_button.clicked.connect(self.open_capture_overlays)
        self.clear_overlay_button.clicked.connect(self.clear_capture_overlays)
        self.mic_plot_nav_button.clicked.connect(self.open_mic_plot)
        self.capture_nav_button.clicked.connect(self.open_capture_overlays)
        self.preferences_nav_button.clicked.connect(self.open_preferences)
        self.about_nav_button.clicked.connect(self.open_about)
        self.plot.scene().sigMouseMoved.connect(self.on_mouse_move)
        self.window.destroyed.connect(self.shutdown)

        self.populate_ports()
        self.update_connection_state(False)
        self.update_status()
        self.mic_markers = load_markers(self.settings)
        self.render_mic_markers()
        self.log(f"RF Bridge v{__version__} ready")

        # Defer connection until after the window is shown and the Qt event loop
        # is running. In a packaged macOS app, doing serial auto-detection during
        # window construction can make the app appear to launch and then vanish.
        if selected_port:
            self.QTimer.singleShot(900, self.connect_device)
        else:
            self.QTimer.singleShot(900, self.try_auto_connect)

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
        QMainWindow, QWidget {{ background: {t['window_bg']}; color: {t['text']}; font-family: Arial, Helvetica, sans-serif; }}
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
        QLabel#connectionStatus {{ font-weight: bold; background: transparent; font-size: 16px; }}
        QLabel#deviceInfoLabel {{ color: {t['muted_text']}; background: transparent; font-size: 12px; padding-top: 2px; }}
        QLabel#deviceNoticeLabel {{ color: {t['disconnected']}; background: transparent; font-size: 12px; padding-top: 2px; }}
        QLabel#overlayHeaderIcon {{ color: {t['text']}; font-size: 26px; font-weight: bold; padding-right: 4px; background: transparent; }}
        QLabel#overlayTitle {{ font-weight: bold; font-family: Menlo, Monaco, Consolas, monospace; font-size: 15px; background: transparent; }}
        QLabel#overlaySubtitle {{ color: {t['muted_text']}; font-size: 12px; background: transparent; }}
        QLabel#overlayEmptyLabel {{ color: {t['text']}; font-size: 16px; font-weight: bold; background: transparent; padding: 2px; }}
        QLabel#overlayEmptyHint {{ color: {t['muted_text']}; font-size: 12px; background: transparent; padding: 2px; }}
        QLabel#sidebarLogo {{ background: transparent; border: 0px; }}
        QLabel#sidebarTitle {{ font-weight: bold; color: {t['text']}; font-size: 24px; background: transparent; }}
        QLabel#sidebarSubtitle {{ color: {t['muted_text']}; font-family: Menlo, Monaco, Consolas, monospace; font-size: 12px; letter-spacing: 0.2px; background: transparent; padding-bottom: 2px; }}
        QPushButton#sidebarButton {{ text-align: left; border: 0px; background: transparent; color: {t['text']}; padding: 9px 12px; border-radius: 7px; }}
        QPushButton#sidebarButton:hover {{ background: {t['button_hover']}; }}
        QPushButton#sidebarButton:disabled {{ color: {t['connected']}; background: {t['hover_bg']}; }}
        QTextEdit#logBox {{ background: {t['log_bg']}; border: 1px solid {t['border']}; border-radius: 6px; color: {t['muted_text']}; font-family: Menlo, Monaco, Consolas, monospace; font-size: 12px; padding: 6px; }}
        QPushButton, QComboBox, QLineEdit {{ background: {t['button_bg']}; color: {t['text']}; border: 1px solid {t['border']}; border-radius: 6px; font-size: 13px; min-height: 32px; padding: 4px 10px; }}
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

        if not preserve_x and self.freqs_mhz:
            self.plot.setXRange(min(self.freqs_mhz), max(self.freqs_mhz), padding=0)

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
        self.freeze_button.setText("Freeze: OFF")
        self.return_live_button.setEnabled(bool(self.latest_dbm and self.live_freqs_mhz))
        self.freqs_mhz = capture["freqs_mhz"]
        self.display_dbm = capture["dbm"]
        self.last_cursor_index = None
        self.peak_curve.setData([], [])
        self.peak_hold = None
        self.peak_history = []

        self.plot.setXRange(min(self.freqs_mhz), max(self.freqs_mhz), padding=0)
        self.lock_plot_axes(preserve_x=True)
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
        self.cursor_line.setPos(self.freqs_mhz[0])
        self.render_mic_markers()
        self.render_scan(self.latest_dbm)
        self.log("Returned to live trace")
        self.update_status()


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
        for item in self.capture_overlay_items:
            try:
                self.plot.removeItem(item)
            except Exception:
                pass
        self.capture_overlay_items = []

        for capture in self.capture_overlays:
            if not capture.get("visible", True):
                continue
            curve = self.plot.plot(
                capture["freqs_mhz"],
                capture["dbm"],
                pen=self.pg.mkPen(capture.get("color", "#33aaff"), width=1.3),
                name=capture.get("name", "Capture"),
            )
            curve.setZValue(2)
            self.capture_overlay_items.append(curve)

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
        if not self.capture_overlays:
            self.overlay_empty_label = QLabel("No overlays loaded")
            self.overlay_empty_label.setObjectName("overlayEmptyLabel")
            self.overlay_empty_label.setAlignment(self.Qt.AlignCenter)
            self.overlay_controls_row.addStretch(1)
            self.overlay_controls_row.addWidget(self.overlay_empty_label)
            self.overlay_controls_row.addStretch(1)
            if hasattr(self, "overlay_empty_hint"):
                self.overlay_empty_hint.setVisible(True)
            return

        if hasattr(self, "overlay_empty_hint"):
            self.overlay_empty_hint.setVisible(False)

        for index, capture in enumerate(self.capture_overlays[:6]):
            label = capture.get("name", f"Capture {index + 1}")
            if len(label) > 24:
                label = label[:21] + "…"
            checkbox = QCheckBox(label)
            checkbox.setChecked(bool(capture.get("visible", True)))
            checkbox.setStyleSheet(f"color: {capture.get('color', self.theme['text'])};")
            checkbox.toggled.connect(lambda checked, i=index: self.set_overlay_visible(i, checked))
            self.overlay_controls_row.addWidget(checkbox)
            self.overlay_checkbox_widgets.append(checkbox)

        if len(self.capture_overlays) > 6:
            more_label = QLabel(f"+{len(self.capture_overlays) - 6} more in Overlays menu")
            more_label.setObjectName("overlayEmptyLabel")
            self.overlay_controls_row.addWidget(more_label)

        self.overlay_controls_row.addStretch(1)

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

        for index, checkbox in enumerate(getattr(self, "overlay_checkbox_widgets", [])):
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
        self.capture_overlays = []
        self.render_capture_overlays()
        self.rebuild_overlay_menu()
        self.log("Capture overlays cleared")
        self.update_status()

    def new_profile(self):
        from PySide6.QtWidgets import QFileDialog, QInputDialog
        from .utils import safe_name

        gig_name, ok = QInputDialog.getText(self.window, "New Gig Profile", "Gig/session name:", text="")
        if not ok:
            return
        gig_name = gig_name.strip()
        if not gig_name:
            self.show_error("Gig/session name is required.")
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

    def render_mic_markers(self):
        for item in self.mic_marker_items:
            try:
                self.plot.removeItem(item)
            except Exception:
                pass
        self.mic_marker_items = []

        if not getattr(self, "plot", None):
            return

        for marker in self.mic_markers:
            if not marker.get("visible", True):
                continue
            freq = float(marker["frequency_mhz"])
            color = marker.get("color", DEFAULT_MARKER_COLOR)
            line = self.pg.InfiniteLine(
                pos=freq,
                angle=90,
                pen=self.pg.mkPen(color, width=1.5),
                movable=False,
            )
            line.setZValue(5)
            label = self.pg.TextItem(
                text=f"{marker['name']}\n{freq:.3f} MHz",
                color=color,
                anchor=(0.5, 0.0),
                fill=self.pg.mkBrush(0, 0, 0, 150),
                border=self.pg.mkPen(color, width=0.75),
            )
            # Place mic plot labels slightly below the top of the graph so
            # labels remain visible instead of clipping against the title area.
            label.setPos(freq, -32)
            label.setZValue(20)
            self.plot.addItem(line, ignoreBounds=True)
            self.plot.addItem(label, ignoreBounds=True)
            self.mic_marker_items.extend([line, label])

    def open_preferences(self):
        from PySide6.QtWidgets import (
            QComboBox,
            QDialog,
            QDialogButtonBox,
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
        refresh_index = refresh_combo.findData(self.refresh_seconds)
        if refresh_index >= 0:
            refresh_combo.setCurrentIndex(refresh_index)

        storage_edit = QLineEdit(self.settings.get_storage_root())
        browse_button = QPushButton("Browse…")
        storage_row = QHBoxLayout()
        storage_row.addWidget(storage_edit, stretch=1)
        storage_row.addWidget(browse_button)

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
        form.addRow("Default storage", storage_row)

        note = QLabel("Storage changes apply to new app sessions. Current scan output stays where this session started.")
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
        self.set_refresh_interval(float(refresh_combo.currentData()))
        self.apply_theme()
        self.log(f"Preferences saved: appearance={self.appearance}, storage={self.settings.get_storage_root()}")

    def log(self, message):
        self.log_box.append(f"[{time_12h()}] {message}")

    def populate_ports(self):
        current = self.port_combo.currentData() or self.selected_port
        self.port_combo.clear()
        self.port_map = {}
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
        try:
            port, header, scanned = find_tinysa_port()
        except Exception as exc:
            self.log(f"Auto-detect skipped: {exc}")
            return
        index = self.port_combo.findData(port)
        if index >= 0:
            self.port_combo.setCurrentIndex(index)
        self.log(f"Auto-detected tinySA: {port}")
        self.auto_connect_in_progress = True
        self.connect_device()

    def connect_device(self):
        if self.connected:
            return
        port = self.port_combo.currentData()
        if not port:
            self.show_error("No serial port selected.")
            return
        self.clear_device_notice()
        self.selected_port = port
        self.settings.set("last_port", port)
        self.update_connection_state(False, "Connecting…")
        self.connect_button.setEnabled(False)
        self.disconnect_button.setEnabled(True)
        self.worker_thread = self.QThread()
        self.worker = ScanWorker(port, self.refresh_seconds, debug_serial=self.debug_serial)
        self.worker.moveToThread(self.worker_thread)
        self.worker_thread.started.connect(self.worker.start)
        self.worker.connected.connect(self.ui_bridge.connected)
        self.worker.scan_ready.connect(self.ui_bridge.scan_ready)
        self.worker.error.connect(self.ui_bridge.error)
        self.worker.log.connect(self.ui_bridge.log)
        self.worker.disconnected.connect(self.ui_bridge.disconnected)
        self.worker.disconnected.connect(self.worker_thread.quit)
        self.worker_thread.finished.connect(self.worker.deleteLater)
        self.worker_thread.finished.connect(self.worker_thread.deleteLater)
        self.worker_thread.finished.connect(self.clear_worker_refs)
        self.worker_thread.start()
        self.log(f"Connecting to {port}")

    def disconnect_device(self):
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

    def on_connected(self, port, version, freqs_mhz):
        self.auto_connect_in_progress = False
        self.connected = True
        self.selected_port = port
        self.freqs_mhz = freqs_mhz
        self.live_freqs_mhz = freqs_mhz.copy()
        self.latest_dbm = []
        self.display_dbm = []
        self.reset_peaks()
        self.plot.setXRange(min(freqs_mhz), max(freqs_mhz), padding=0)
        self.lock_plot_axes(preserve_x=True)
        self.cursor_line.setPos(freqs_mhz[0])
        self.render_mic_markers()
        self.device_info_label.setText(
            f"Device: {version or 'tinySA'}\n"
            f"Range: {min(freqs_mhz):.3f}–{max(freqs_mhz):.3f} MHz"
        )
        self.clear_device_notice()
        self.update_connection_state(True, "Connected")
        self.log(f"Frequency range: {min(freqs_mhz):.3f}–{max(freqs_mhz):.3f} MHz")

    def on_disconnected(self):
        was_connected = self.connected
        self.connected = False
        self.update_connection_state(False)
        if was_connected:
            self.log("Disconnected")

    def on_worker_error(self, message):
        if self.shutting_down:
            return

        message_text = str(message)
        self.log(message_text)
        lowered = message_text.lower()

        transient_empty_read = (
            "returned no data" in lowered
            or "no frequency points" in lowered
            or "frequency range" in lowered
        )

        if transient_empty_read:
            self.scan_error_count += 1
            self.log("tinySA did not return data yet; leaving the UI open for retry/reconnect")
            self.show_device_notice(
                "tinySA is not returning data. Reboot/power-cycle the tinySA, then reconnect."
            )
            self.update_connection_state(False, "Disconnected — tinySA not ready")
            self.auto_connect_in_progress = False
            self.disconnect_device()
            # Do not show a modal startup warning for this recoverable case. The
            # app should stay usable for capture overlays and manual reconnect.
            return

        # Auto-connect should never block app startup with a modal error.
        # Manual non-transient errors still show the warning so troubleshooting is obvious.
        if self.auto_connect_in_progress:
            self.auto_connect_in_progress = False
            self.disconnect_device()
            self.update_connection_state(False, "Disconnected — tinySA not ready")
            return
        self.show_error(message_text)

    def update_connection_state(self, connected, text=None):
        self.connected = connected
        self.status_dot.setStyleSheet(f"color: {self.theme['connected'] if connected else self.theme['disconnected']};")
        self.connection_status.setText(text or ("Connected" if connected else "Disconnected"))
        show_disconnect = connected or self.worker is not None
        self.connect_button.setVisible(not show_disconnect)
        self.refresh_ports_button.setVisible(not show_disconnect)
        self.disconnect_button.setVisible(show_disconnect)
        self.connect_button.setEnabled(not connected)
        self.disconnect_button.setEnabled(show_disconnect)
        self.refresh_ports_button.setEnabled(not connected)
        self.port_combo.setEnabled(not connected)
        if not connected:
            self.device_info_label.setText("Device: —\nRange: —")
        self.update_status()

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
        self.refresh_button.setText(f"Refresh: {format_seconds(seconds)}s")
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
        self.refresh_index = (self.refresh_index + 1) % len(REFRESH_MODES)
        self.set_refresh_interval(REFRESH_MODES[self.refresh_index])

    def toggle_freeze(self):
        self.frozen = not self.frozen
        self.freeze_button.setText(f"Freeze: {'ON' if self.frozen else 'OFF'}")
        self.log("Trace frozen" if self.frozen else "Trace resumed")
        if not self.frozen and self.latest_dbm and self.freqs_mhz:
            self.render_scan(self.latest_dbm)

    def toggle_peak(self):
        self.peak_mode_index = (self.peak_mode_index + 1) % len(PEAK_MODES)
        self.settings.set("peak_mode_index", self.peak_mode_index)
        label, window_seconds = PEAK_MODES[self.peak_mode_index]
        self.peak_button.setText(f"Peak: {label}")
        if label == "OFF":
            self.peak_enabled = False
            self.peak_hold = None
            self.peak_history = []
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
        self.peak_history = []
        self.peak_button.setText("Peak: OFF")
        self.peak_curve.setData([], [])
        self.update_hover_label(None)

    def on_scan_ready(self, dbm):
        self.scan_error_count = 0
        live_freqs = self.live_freqs_mhz or self.freqs_mhz
        if not live_freqs:
            return
        if len(dbm) != len(live_freqs):
            self.log(f"Warning: frequency/data mismatch: {len(live_freqs)} freqs, {len(dbm)} levels")
            return
        self.latest_dbm = dbm
        if self.capture_mode:
            self.return_live_button.setEnabled(True)
        else:
            self.freqs_mhz = live_freqs
            self.last_cursor_index = None
            if not self.frozen:
                self.render_scan(dbm)
        now = time.time()
        if now - self.last_save_time >= SCAN_INTERVAL_SECONDS:
            filename, latest_filename = save_wwb_csv(self.output_dir, self.gig_slug, live_freqs, dbm)
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
                self.peak_history = [sample for sample in self.peak_history if sample[0] >= cutoff]
                if self.peak_history:
                    samples = [sample[1] for sample in self.peak_history]
                    self.peak_hold = [max(values) for values in zip(*samples)]
            if self.peak_hold:
                self.peak_curve.setData(self.freqs_mhz, self.peak_hold)
        self.live_curve.setData(self.freqs_mhz, dbm)
        self.render_capture_overlays()
        self.update_top_frequencies(dbm)
        self.lock_plot_axes(preserve_x=True)
        self.plot.setTitle(f"RF Bridge - {self.gig_slug} - {time_12h()}", color=self.theme["text"], size="16pt")

    def update_top_frequencies(self, dbm):
        median_floor = sorted(dbm)[len(dbm) // 2]
        strongest = sorted(zip(self.freqs_mhz, dbm), key=lambda pair: pair[1], reverse=True)[:8]
        text = "RF SUMMARY\n──────────────────────\n\n"
        text += "Median Floor\n"
        text += f"{median_floor:7.2f} dBm\n\n"
        text += "TOP 8 RF HITS\n──────────────────────\n"
        for i, (freq, level) in enumerate(strongest, start=1):
            text += f"{i}. {freq:9.3f} MHz  {level:7.2f} dBm\n"
        self.summary_label.setText(text)
        for marker in self.top_markers:
            self.plot.removeItem(marker)
        self.top_markers = []
        for freq, level in strongest:
            marker = self.pg.InfiniteLine(pos=freq, angle=90, pen=self.pg.mkPen(self.theme["marker"], width=1, style=self.Qt.DotLine))
            marker.setZValue(-10)
            self.plot.addItem(marker, ignoreBounds=True)
            self.top_markers.append(marker)

    def update_hover_label(self, idx):
        source = self.display_dbm or self.latest_dbm
        if idx is None or not source or not self.freqs_mhz:
            self.hover_label.setText("Hover over the graph for live readout.")
            return
        nearest_freq = self.freqs_mhz[idx]
        nearest_level = source[idx]
        if self.capture_mode and self.loaded_capture:
            mode_text = f"\nLoaded Capture: {self.loaded_capture['name']}"
        else:
            mode_text = "\nFrozen Trace" if self.frozen else ""
        if self.peak_hold:
            nearest_peak = self.peak_hold[idx]
            self.hover_label.setText(f"{nearest_freq:.6f} MHz\nLive: {nearest_level:.2f} dBm\nPeak: {nearest_peak:.2f} dBm{mode_text}")
        else:
            self.hover_label.setText(f"{nearest_freq:.6f} MHz\nLive: {nearest_level:.2f} dBm{mode_text}")

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
            freeze_label = f"Loaded Capture: {self.loaded_capture['name']}"
        else:
            freeze_label = "Frozen" if self.frozen else "Live"
        overlay_count = sum(1 for capture in self.capture_overlays if capture.get("visible", True))
        self.status_label.setText(
            f"Scan Folder: {self.output_dir}   |   Latest: latest_scan.csv   |   "
            f"Next Save: {minutes}:{seconds:02d}   |   Refresh: {format_seconds(self.refresh_seconds)}s   |   "
            f"Mode: {freeze_label}   |   Overlays: {overlay_count}   |   tinySA: {self.selected_port or 'not connected'}"
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

        self.worker = None
        self.worker_thread = None
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

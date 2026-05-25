"""PySide6 / pyqtgraph RF Bridge v1.5 UI."""

import bisect
import os
import time

from .config import SCAN_INTERVAL_SECONDS, UI_UPDATE_SECONDS
from .export import save_wwb_csv
from .settings import AppSettings
from .tinysa import candidate_serial_ports, describe_port, find_tinysa_port
from .utils import time_12h
from .worker import ScanWorker


REFRESH_MODES = [0.5, 1, 2, 5, 10]
PEAK_MODES = [
    ("OFF", None),
    ("LATCH", "latch"),
    ("1 min", 60),
    ("5 min", 300),
    ("15 min", 900),
]


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
    def __init__(self, output_dir, gig_slug, ui_update_seconds=UI_UPDATE_SECONDS, selected_port=None):
        from PySide6.QtCore import Qt, QThread, Signal, QMetaObject, Q_ARG, QTimer
        from PySide6.QtWidgets import (
            QApplication,
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
        self.pg = pg

        self.output_dir = output_dir
        self.gig_slug = gig_slug
        self.selected_port = selected_port
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
        self.frozen = False
        self.connected = False
        self.worker_thread = None
        self.worker = None
        self.port_map = {}
        self.settings = AppSettings()
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
        self.window = QMainWindow()
        self.window.setWindowTitle("RF Bridge")
        self.window.resize(1580, 920)

        saved_geometry = self.settings.get_bytes("window_geometry")
        if saved_geometry:
            self.window.restoreGeometry(saved_geometry)

        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(18, 18, 18, 14)
        root_layout.setSpacing(12)

        connection_panel = QFrame()
        connection_panel.setObjectName("connectionPanel")
        connection_layout = QGridLayout(connection_panel)
        connection_layout.setContentsMargins(14, 12, 14, 12)
        connection_layout.setHorizontalSpacing(10)
        connection_layout.setVerticalSpacing(8)

        self.status_dot = QLabel("●")
        self.status_dot.setObjectName("statusDot")
        self.connection_status = QLabel("Disconnected")
        self.connection_status.setObjectName("connectionStatus")
        self.port_combo = QComboBox()
        self.refresh_ports_button = QPushButton("Refresh Ports")
        self.connect_button = QPushButton("Connect")
        self.disconnect_button = QPushButton("Disconnect")
        self.disconnect_button.setEnabled(False)
        self.version_label = QLabel("Device: —")
        self.range_label = QLabel("Range: —")

        connection_layout.addWidget(self.status_dot, 0, 0)
        connection_layout.addWidget(self.connection_status, 0, 1)
        connection_layout.addWidget(QLabel("tinySA Port"), 0, 2)
        connection_layout.addWidget(self.port_combo, 0, 3)
        connection_layout.addWidget(self.refresh_ports_button, 0, 4)
        connection_layout.addWidget(self.connect_button, 0, 5)
        connection_layout.addWidget(self.disconnect_button, 0, 6)
        connection_layout.addWidget(self.version_label, 1, 3, 1, 2)
        connection_layout.addWidget(self.range_label, 1, 5, 1, 2)
        connection_layout.setColumnStretch(3, 1)

        content_layout = QHBoxLayout()
        content_layout.setSpacing(18)

        pg.setConfigOptions(antialias=True)
        self.plot = pg.PlotWidget()
        self.plot.setBackground("#181818")
        self.plot.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.plot.showGrid(x=True, y=True, alpha=0.25)
        self.plot.setLabel("bottom", "Frequency", units="MHz")
        self.plot.setLabel("left", "Amplitude", units="dBm")
        self.plot.setTitle(f"RF Bridge - {self.gig_slug}", color="#eeeeee", size="16pt")
        self.plot.setYRange(-110, -20, padding=0)

        axis_pen = pg.mkPen("#888888")
        self.plot.getAxis("bottom").setPen(axis_pen)
        self.plot.getAxis("left").setPen(axis_pen)
        self.plot.getAxis("bottom").setTextPen("#dddddd")
        self.plot.getAxis("left").setTextPen("#dddddd")

        self.live_curve = self.plot.plot([], [], pen=pg.mkPen("#00ff99", width=2), name="Live")
        self.peak_curve = self.plot.plot([], [], pen=pg.mkPen("#ff3333", width=1.5), name="Peak Hold")
        self.threshold_85 = pg.InfiniteLine(pos=-85, angle=0, pen=pg.mkPen("#ffaa00", width=1, style=self.Qt.DashLine))
        self.threshold_60 = pg.InfiniteLine(pos=-60, angle=0, pen=pg.mkPen("#ff00aa", width=1, style=self.Qt.DashLine))
        self.plot.addItem(self.threshold_85)
        self.plot.addItem(self.threshold_60)
        self.cursor_line = pg.InfiniteLine(pos=0, angle=90, pen=pg.mkPen("#00ff99", width=1))
        self.cursor_line.setVisible(False)
        self.plot.addItem(self.cursor_line)

        side_panel = QFrame()
        side_panel.setObjectName("sidePanel")
        side_panel.setFixedWidth(350)
        side_layout = QVBoxLayout(side_panel)
        side_layout.setContentsMargins(16, 16, 16, 16)
        side_layout.setSpacing(12)

        self.summary_label = QLabel("RF SUMMARY\n──────────────────────\n\nConnect to tinySA to begin.")
        self.summary_label.setObjectName("summaryLabel")
        self.summary_label.setAlignment(self.Qt.AlignTop | self.Qt.AlignLeft)
        self.summary_label.setTextInteractionFlags(self.Qt.TextSelectableByMouse)
        self.hover_label = QLabel("Hover over the graph for live readout.")
        self.hover_label.setObjectName("hoverLabel")
        self.hover_label.setAlignment(self.Qt.AlignTop | self.Qt.AlignLeft)
        self.hover_label.setTextInteractionFlags(self.Qt.TextSelectableByMouse)

        self.peak_button = QPushButton("Peak: OFF")
        self.reset_button = QPushButton("Reset Peaks")
        self.refresh_button = QPushButton(f"Refresh: {format_seconds(self.refresh_seconds)}s")
        self.freeze_button = QPushButton("Freeze: OFF")
        for button in (self.peak_button, self.reset_button, self.refresh_button, self.freeze_button):
            button.setMinimumHeight(42)

        side_layout.addWidget(self.summary_label, stretch=1)
        side_layout.addWidget(self.hover_label)
        side_layout.addWidget(self.peak_button)
        side_layout.addWidget(self.reset_button)
        side_layout.addWidget(self.refresh_button)
        side_layout.addWidget(self.freeze_button)

        content_layout.addWidget(self.plot, stretch=1)
        content_layout.addWidget(side_panel)

        self.log_box = QTextEdit()
        self.log_box.setObjectName("logBox")
        self.log_box.setReadOnly(True)
        self.log_box.setMaximumHeight(125)
        self.status_label = QLabel("")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setMinimumHeight(38)
        self.status_label.setTextInteractionFlags(self.Qt.TextSelectableByMouse)

        root_layout.addWidget(connection_panel)
        root_layout.addLayout(content_layout, stretch=1)
        root_layout.addWidget(self.log_box)
        root_layout.addWidget(self.status_label)
        self.window.setCentralWidget(root)

        self.window.setStyleSheet(self.stylesheet())

        self.refresh_ports_button.clicked.connect(self.populate_ports)
        self.connect_button.clicked.connect(self.connect_device)
        self.disconnect_button.clicked.connect(self.disconnect_device)
        self.peak_button.clicked.connect(self.toggle_peak)
        self.reset_button.clicked.connect(self.reset_peaks)
        self.refresh_button.clicked.connect(self.toggle_refresh)
        self.freeze_button.clicked.connect(self.toggle_freeze)
        self.plot.scene().sigMouseMoved.connect(self.on_mouse_move)
        self.window.destroyed.connect(self.shutdown)

        self.populate_ports()
        self.update_connection_state(False)
        self.update_status()
        self.log("RF Bridge v1.6.2 ready")

        # Defer connection until after the window is shown and the Qt event loop
        # is running. In a packaged macOS app, doing serial auto-detection during
        # window construction can make the app appear to launch and then vanish.
        if selected_port:
            self.QTimer.singleShot(250, self.connect_device)
        else:
            self.QTimer.singleShot(250, self.try_auto_connect)

    def stylesheet(self):
        return """
        QMainWindow, QWidget { background: #111111; color: #eeeeee; font-family: Arial, Helvetica, sans-serif; }
        QFrame#connectionPanel { background: #181818; border: 1px solid #444444; border-radius: 8px; }
        QFrame#sidePanel { background: #141414; border-left: 1px solid #555555; }
        QLabel#summaryLabel, QLabel#hoverLabel { color: #eeeeee; font-family: Menlo, Monaco, Consolas, monospace; font-size: 13px; }
        QLabel#hoverLabel { background: #202020; border: 1px solid #444444; border-radius: 6px; padding: 8px; }
        QLabel#statusLabel { background: #181818; border: 1px solid #555555; border-radius: 6px; color: #eeeeee; font-family: Menlo, Monaco, Consolas, monospace; font-size: 12px; padding-left: 14px; }
        QLabel#statusDot { color: #aa3333; font-size: 22px; }
        QLabel#connectionStatus { font-weight: bold; }
        QTextEdit#logBox { background: #0f0f0f; border: 1px solid #444444; border-radius: 6px; color: #dddddd; font-family: Menlo, Monaco, Consolas, monospace; font-size: 12px; padding: 6px; }
        QPushButton, QComboBox { background: #222222; color: #eeeeee; border: 1px solid #555555; border-radius: 6px; font-size: 13px; min-height: 32px; padding: 4px 10px; }
        QPushButton:hover, QComboBox:hover { background: #333333; }
        QPushButton:pressed { background: #444444; }
        QPushButton:disabled { color: #777777; background: #191919; }
        """

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
        self.connect_device()

    def connect_device(self):
        if self.connected:
            return
        port = self.port_combo.currentData()
        if not port:
            self.show_error("No serial port selected.")
            return
        self.selected_port = port
        self.settings.set("last_port", port)
        self.update_connection_state(False, "Connecting…")
        self.connect_button.setEnabled(False)
        self.disconnect_button.setEnabled(True)
        self.worker_thread = self.QThread()
        self.worker = ScanWorker(port, self.refresh_seconds)
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
        self.connected = True
        self.selected_port = port
        self.freqs_mhz = freqs_mhz
        self.latest_dbm = []
        self.display_dbm = []
        self.reset_peaks()
        self.plot.setXRange(min(freqs_mhz), max(freqs_mhz), padding=0)
        self.cursor_line.setPos(freqs_mhz[0])
        self.version_label.setText(f"Device: {version or 'tinySA'}")
        self.range_label.setText(f"Range: {min(freqs_mhz):.3f}–{max(freqs_mhz):.3f} MHz")
        self.update_connection_state(True, f"Connected: {port}")
        self.log(f"Frequency range: {min(freqs_mhz):.3f}–{max(freqs_mhz):.3f} MHz")

    def on_disconnected(self):
        was_connected = self.connected
        self.connected = False
        self.update_connection_state(False)
        if was_connected:
            self.log("Disconnected")

    def on_worker_error(self, message):
        self.log(message)
        self.show_error(message)

    def update_connection_state(self, connected, text=None):
        self.connected = connected
        self.status_dot.setStyleSheet(f"color: {'#33cc77' if connected else '#aa3333'};")
        self.connection_status.setText(text or ("Connected" if connected else "Disconnected"))
        self.connect_button.setEnabled(not connected)
        self.disconnect_button.setEnabled(connected or self.worker is not None)
        self.refresh_ports_button.setEnabled(not connected)
        self.port_combo.setEnabled(not connected)
        if not connected:
            self.version_label.setText("Device: —")
            self.range_label.setText("Range: —")
        self.update_status()

    def show_error(self, message):
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
        if not self.freqs_mhz:
            return
        if len(dbm) != len(self.freqs_mhz):
            self.log(f"Warning: frequency/data mismatch: {len(self.freqs_mhz)} freqs, {len(dbm)} levels")
            return
        self.latest_dbm = dbm
        self.last_cursor_index = None
        if not self.frozen:
            self.render_scan(dbm)
        now = time.time()
        if now - self.last_save_time >= SCAN_INTERVAL_SECONDS:
            filename, latest_filename = save_wwb_csv(self.output_dir, self.gig_slug, self.freqs_mhz, dbm)
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
        self.update_top_frequencies(dbm)
        self.plot.setTitle(f"RF Bridge - {self.gig_slug} - {time_12h()}", color="#eeeeee", size="16pt")

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
            marker = self.pg.InfiniteLine(pos=freq, angle=90, pen=self.pg.mkPen("#666666", width=1, style=self.Qt.DotLine))
            marker.setZValue(-10)
            self.plot.addItem(marker)
            self.top_markers.append(marker)

    def update_hover_label(self, idx):
        source = self.display_dbm or self.latest_dbm
        if idx is None or not source or not self.freqs_mhz:
            self.hover_label.setText("Hover over the graph for live readout.")
            return
        nearest_freq = self.freqs_mhz[idx]
        nearest_level = source[idx]
        frozen_text = "\nFrozen Trace" if self.frozen else ""
        if self.peak_hold:
            nearest_peak = self.peak_hold[idx]
            self.hover_label.setText(f"{nearest_freq:.6f} MHz\nLive: {nearest_level:.2f} dBm\nPeak: {nearest_peak:.2f} dBm{frozen_text}")
        else:
            self.hover_label.setText(f"{nearest_freq:.6f} MHz\nLive: {nearest_level:.2f} dBm{frozen_text}")

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
        freeze_label = "Frozen" if self.frozen else "Live"
        self.status_label.setText(
            f"Scan Folder: {self.output_dir}   |   Latest: latest_scan.csv   |   "
            f"Next Save: {minutes}:{seconds:02d}   |   Refresh: {format_seconds(self.refresh_seconds)}s   |   "
            f"Mode: {freeze_label}   |   tinySA: {self.selected_port or 'not connected'}"
        )

    def shutdown(self):
        self.settings.set("window_geometry", self.window.saveGeometry())
        if self.worker is not None:
            self.QMetaObject.invokeMethod(
                self.worker,
                "stop",
                self.Qt.QueuedConnection,
            )

    def run(self):
        self.window.show()
        exit_code = self.app.exec()
        self.shutdown()
        return exit_code


def run_ui(output_dir, gig_slug, ui_update_seconds=UI_UPDATE_SECONDS, selected_port=None):
    window = RFBridgeWindow(
        output_dir=output_dir,
        gig_slug=gig_slug,
        ui_update_seconds=ui_update_seconds,
        selected_port=selected_port,
    )
    return window.run()

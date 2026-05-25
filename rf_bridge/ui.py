"""PySide6 / pyqtgraph RF Bridge v1.4 UI.

This replaces the Matplotlib UI while preserving the same scan/export behavior.
"""

import bisect
import time

from .config import SCAN_INTERVAL_SECONDS, UI_UPDATE_SECONDS
from .export import save_wwb_csv
from .scanner import read_scan_dbm
from .utils import time_12h


REFRESH_MODES = [0.5, 1, 2, 5, 10]
PEAK_MODES = [
    ("OFF", None),
    ("LATCH", "latch"),
    ("1 min", 60),
    ("5 min", 300),
    ("15 min", 900),
]


def format_seconds(seconds):
    if float(seconds).is_integer():
        return str(int(seconds))
    return str(seconds)


class RFBridgeWindow:
    """Small wrapper so run_ui can stay as the public UI entrypoint."""

    def __init__(self, ser, output_dir, gig_slug, freqs_mhz, ui_update_seconds, selected_port):
        from PySide6.QtCore import Qt, QTimer
        from PySide6.QtWidgets import (
            QApplication,
            QFrame,
            QHBoxLayout,
            QLabel,
            QMainWindow,
            QPushButton,
            QSizePolicy,
            QVBoxLayout,
            QWidget,
        )
        import pyqtgraph as pg

        self.Qt = Qt
        self.QTimer = QTimer
        self.pg = pg

        self.ser = ser
        self.output_dir = output_dir
        self.gig_slug = gig_slug
        self.freqs_mhz = freqs_mhz
        self.selected_port = selected_port or "auto"

        self.latest_dbm = []
        self.last_save_time = 0
        self.last_cursor_index = None
        self.peak_mode_index = 0
        self.peak_enabled = False
        self.peak_hold = None
        self.peak_history = []
        self.top_markers = []

        self.refresh_index = min(
            range(len(REFRESH_MODES)),
            key=lambda index: abs(REFRESH_MODES[index] - ui_update_seconds),
        )
        self.refresh_seconds = REFRESH_MODES[self.refresh_index]

        self.app = QApplication.instance() or QApplication([])
        self.window = QMainWindow()
        self.window.setWindowTitle("RF Bridge")
        self.window.resize(1500, 850)

        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(18, 18, 18, 14)
        root_layout.setSpacing(12)

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
        self.plot.setXRange(min(freqs_mhz), max(freqs_mhz), padding=0)
        self.plot.setYRange(-110, -20, padding=0)

        axis_pen = pg.mkPen("#888888")
        self.plot.getAxis("bottom").setPen(axis_pen)
        self.plot.getAxis("left").setPen(axis_pen)
        self.plot.getAxis("bottom").setTextPen("#dddddd")
        self.plot.getAxis("left").setTextPen("#dddddd")

        self.live_curve = self.plot.plot(
            [],
            [],
            pen=pg.mkPen("#00ff99", width=2),
            name="Live",
        )
        self.peak_curve = self.plot.plot(
            [],
            [],
            pen=pg.mkPen("#ff3333", width=1.5),
            name="Peak Hold",
        )

        self.threshold_85 = pg.InfiniteLine(
            pos=-85,
            angle=0,
            pen=pg.mkPen("#ffaa00", width=1, style=self.Qt.DashLine),
        )
        self.threshold_60 = pg.InfiniteLine(
            pos=-60,
            angle=0,
            pen=pg.mkPen("#ff00aa", width=1, style=self.Qt.DashLine),
        )
        self.plot.addItem(self.threshold_85)
        self.plot.addItem(self.threshold_60)

        self.cursor_line = pg.InfiniteLine(
            pos=freqs_mhz[0],
            angle=90,
            pen=pg.mkPen("#00ff99", width=1),
        )
        self.cursor_line.setVisible(False)
        self.plot.addItem(self.cursor_line)

        side_panel = QFrame()
        side_panel.setObjectName("sidePanel")
        side_panel.setFixedWidth(330)
        side_layout = QVBoxLayout(side_panel)
        side_layout.setContentsMargins(16, 16, 16, 16)
        side_layout.setSpacing(12)

        self.summary_label = QLabel("RF SUMMARY\n──────────────────────\n\nWaiting for scan...")
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

        for button in (self.peak_button, self.reset_button, self.refresh_button):
            button.setMinimumHeight(42)

        side_layout.addWidget(self.summary_label, stretch=1)
        side_layout.addWidget(self.hover_label)
        side_layout.addWidget(self.peak_button)
        side_layout.addWidget(self.reset_button)
        side_layout.addWidget(self.refresh_button)

        content_layout.addWidget(self.plot, stretch=1)
        content_layout.addWidget(side_panel)

        self.status_label = QLabel("")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setMinimumHeight(46)
        self.status_label.setTextInteractionFlags(self.Qt.TextSelectableByMouse)

        root_layout.addLayout(content_layout, stretch=1)
        root_layout.addWidget(self.status_label)
        self.window.setCentralWidget(root)

        self.window.setStyleSheet(
            """
            QMainWindow, QWidget {
                background: #111111;
                color: #eeeeee;
                font-family: Arial, Helvetica, sans-serif;
            }
            QFrame#sidePanel {
                background: #141414;
                border-left: 1px solid #555555;
            }
            QLabel#summaryLabel, QLabel#hoverLabel {
                color: #eeeeee;
                font-family: Menlo, Monaco, Consolas, monospace;
                font-size: 13px;
            }
            QLabel#hoverLabel {
                background: #202020;
                border: 1px solid #444444;
                border-radius: 6px;
                padding: 8px;
            }
            QLabel#statusLabel {
                background: #181818;
                border: 1px solid #555555;
                border-radius: 6px;
                color: #eeeeee;
                font-family: Menlo, Monaco, Consolas, monospace;
                font-size: 12px;
                padding-left: 14px;
            }
            QPushButton {
                background: #222222;
                color: #eeeeee;
                border: 1px solid #555555;
                border-radius: 6px;
                font-size: 13px;
            }
            QPushButton:hover {
                background: #333333;
            }
            QPushButton:pressed {
                background: #444444;
            }
            """
        )

        self.peak_button.clicked.connect(self.toggle_peak)
        self.reset_button.clicked.connect(self.reset_peaks)
        self.refresh_button.clicked.connect(self.toggle_refresh)
        self.plot.scene().sigMouseMoved.connect(self.on_mouse_move)

        self.scan_timer = self.QTimer()
        self.scan_timer.timeout.connect(self.update_scan)

        self.status_timer = self.QTimer()
        self.status_timer.timeout.connect(self.update_status)
        self.status_timer.start(1000)

        self.set_refresh_interval(self.refresh_seconds)
        self.update_scan()

    def nearest_index(self, freq):
        idx = bisect.bisect_left(self.freqs_mhz, freq)

        if idx <= 0:
            return 0

        if idx >= len(self.freqs_mhz):
            return len(self.freqs_mhz) - 1

        before = idx - 1
        after = idx

        if abs(self.freqs_mhz[before] - freq) <= abs(self.freqs_mhz[after] - freq):
            return before

        return after

    def set_refresh_interval(self, seconds):
        self.refresh_seconds = seconds
        self.refresh_button.setText(f"Refresh: {format_seconds(seconds)}s")
        self.scan_timer.start(int(seconds * 1000))
        print(f"UI refresh changed to {seconds} seconds")
        self.update_status()

    def toggle_refresh(self):
        self.refresh_index = (self.refresh_index + 1) % len(REFRESH_MODES)
        self.set_refresh_interval(REFRESH_MODES[self.refresh_index])

    def toggle_peak(self):
        self.peak_mode_index = (self.peak_mode_index + 1) % len(PEAK_MODES)
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

    def reset_peaks(self):
        self.peak_enabled = False
        self.peak_mode_index = 0
        self.peak_hold = None
        self.peak_history = []
        self.peak_button.setText("Peak: OFF")
        self.peak_curve.setData([], [])
        self.update_hover_label(None)

    def update_top_frequencies(self, dbm):
        median_floor = sorted(dbm)[len(dbm) // 2]
        strongest = sorted(
            zip(self.freqs_mhz, dbm),
            key=lambda pair: pair[1],
            reverse=True,
        )[:8]

        text = "RF SUMMARY\n"
        text += "──────────────────────\n\n"
        text += "Median Floor\n"
        text += f"{median_floor:7.2f} dBm\n\n"
        text += "TOP 8 RF HITS\n"
        text += "──────────────────────\n"

        for i, (freq, level) in enumerate(strongest, start=1):
            text += f"{i}. {freq:9.3f} MHz  {level:7.2f} dBm\n"

        self.summary_label.setText(text)

        for marker in self.top_markers:
            self.plot.removeItem(marker)
        self.top_markers = []

        for freq, level in strongest:
            marker = self.pg.InfiniteLine(
                pos=freq,
                angle=90,
                pen=self.pg.mkPen("#666666", width=1, style=self.Qt.DotLine),
            )
            marker.setZValue(-10)
            self.plot.addItem(marker)
            self.top_markers.append(marker)

    def update_hover_label(self, idx):
        if idx is None or not self.latest_dbm:
            self.hover_label.setText("Hover over the graph for live readout.")
            return

        nearest_freq = self.freqs_mhz[idx]
        nearest_level = self.latest_dbm[idx]

        if self.peak_hold:
            nearest_peak = self.peak_hold[idx]
            self.hover_label.setText(
                f"{nearest_freq:.6f} MHz\n"
                f"Live: {nearest_level:.2f} dBm\n"
                f"Peak: {nearest_peak:.2f} dBm"
            )
        else:
            self.hover_label.setText(
                f"{nearest_freq:.6f} MHz\n"
                f"Live: {nearest_level:.2f} dBm"
            )

    def on_mouse_move(self, scene_pos):
        if not self.latest_dbm:
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

    def update_scan(self):
        try:
            dbm = read_scan_dbm(self.ser)
        except Exception as exc:
            self.status_label.setText(f"Scan error: {exc}")
            return

        if len(dbm) != len(self.freqs_mhz):
            print(
                f"Warning: frequency/data mismatch: "
                f"{len(self.freqs_mhz)} freqs, "
                f"{len(dbm)} levels"
            )
            return

        self.latest_dbm = dbm
        self.last_cursor_index = None

        if self.peak_enabled:
            now = time.time()
            label, window_seconds = PEAK_MODES[self.peak_mode_index]
            self.peak_history.append((now, dbm.copy()))

            if window_seconds == "latch":
                if self.peak_hold is None:
                    self.peak_hold = dbm.copy()
                else:
                    self.peak_hold = [
                        max(old, new)
                        for old, new in zip(self.peak_hold, dbm)
                    ]
            else:
                cutoff = now - window_seconds
                self.peak_history = [
                    sample
                    for sample in self.peak_history
                    if sample[0] >= cutoff
                ]

                if self.peak_history:
                    samples = [sample[1] for sample in self.peak_history]
                    self.peak_hold = [max(values) for values in zip(*samples)]

            if self.peak_hold:
                self.peak_curve.setData(self.freqs_mhz, self.peak_hold)

        self.live_curve.setData(self.freqs_mhz, dbm)
        self.update_top_frequencies(dbm)
        self.plot.setTitle(f"RF Bridge - {self.gig_slug} - {time_12h()}", color="#eeeeee", size="16pt")

        now = time.time()
        if now - self.last_save_time >= SCAN_INTERVAL_SECONDS:
            print("=" * 50)
            print(f"Captured {len(dbm)} scan points at {time_12h()}")
            save_wwb_csv(self.output_dir, self.gig_slug, self.freqs_mhz, dbm)
            self.last_save_time = now

        self.update_status(now)

    def update_status(self, now=None):
        if now is None:
            now = time.time()

        if self.last_save_time:
            next_save = max(0, SCAN_INTERVAL_SECONDS - int(now - self.last_save_time))
        else:
            next_save = 0

        minutes = next_save // 60
        seconds = next_save % 60

        self.status_label.setText(
            f"Scan Folder: {self.output_dir}   |   "
            f"Latest: latest_scan.csv   |   "
            f"Next Save: {minutes}:{seconds:02d}   |   "
            f"Refresh: {format_seconds(self.refresh_seconds)}s   |   "
            f"tinySA: {self.selected_port}"
        )

    def run(self):
        self.window.show()
        self.app.exec()


def run_ui(ser, output_dir, gig_slug, freqs_mhz, ui_update_seconds=UI_UPDATE_SECONDS, selected_port=None):
    window = RFBridgeWindow(
        ser=ser,
        output_dir=output_dir,
        gig_slug=gig_slug,
        freqs_mhz=freqs_mhz,
        ui_update_seconds=ui_update_seconds,
        selected_port=selected_port,
    )
    window.run()

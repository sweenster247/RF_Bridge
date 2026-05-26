"""Threaded tinySA scan worker for the PySide6 UI."""

import time

import serial
from PySide6.QtCore import QObject, QTimer, Signal, Slot

from .config import BAUD, TINYSA_SERIAL_TIMEOUT_SECONDS, TINYSA_STARTUP_SETTLE_SECONDS
from .scanner import read_frequencies_mhz, read_scan_dbm
from .tinysa import send_command


class ScanWorker(QObject):
    """Own the serial connection and polling timer inside a QThread."""

    connected = Signal(str, str, list)       # port, version, freqs_mhz
    scan_ready = Signal(list)                # dbm values
    disconnected = Signal()
    error = Signal(str)
    log = Signal(str)

    def __init__(self, port, refresh_seconds, baud=BAUD):
        super().__init__()
        self.port = port
        self.refresh_seconds = refresh_seconds
        self.baud = baud
        self.ser = None
        self.timer = None
        self.freqs_mhz = []
        self.running = False
        self._stopped_emitted = False

    @Slot()
    def start(self):
        try:
            self.ser = serial.Serial(self.port, self.baud, timeout=TINYSA_SERIAL_TIMEOUT_SECONDS)
            self.log.emit(f"Waiting {TINYSA_STARTUP_SETTLE_SECONDS:g}s for tinySA console…")
            time.sleep(TINYSA_STARTUP_SETTLE_SECONDS)

            version = send_command(self.ser, "version").strip()
            self.log.emit("Reading tinySA frequency range…")
            self.freqs_mhz = read_frequencies_mhz(self.ser)

            self.running = True
            self.connected.emit(self.port, version, self.freqs_mhz)
            self.log.emit(f"Connected to {self.port}")

            self.timer = QTimer(self)
            self.timer.timeout.connect(self.poll)
            self.timer.start(int(self.refresh_seconds * 1000))
            self.poll()

        except Exception as exc:
            self.error.emit(str(exc))
            self.stop()

    @Slot(float)
    def set_refresh_seconds(self, seconds):
        self.refresh_seconds = seconds
        if self.timer is not None:
            self.timer.start(int(seconds * 1000))
        self.log.emit(f"Refresh changed to {seconds:g}s")

    @Slot()
    def poll(self):
        if not self.running or self.ser is None:
            return

        try:
            dbm = read_scan_dbm(self.ser)
        except Exception as exc:
            # During app shutdown the serial port may already be closing. Do not
            # surface that as a user-facing scan error.
            if self.running:
                self.error.emit(f"Scan error: {exc}")
            self.stop()
            return

        if self.running:
            self.scan_ready.emit(dbm)

    @Slot()
    def stop(self):
        if self._stopped_emitted:
            return

        self.running = False

        if self.timer is not None:
            try:
                self.timer.stop()
            except Exception:
                pass
            self.timer.deleteLater()
            self.timer = None

        if self.ser is not None:
            try:
                if self.ser.is_open:
                    self.ser.close()
            except Exception:
                pass
            self.ser = None

        self._stopped_emitted = True
        self.disconnected.emit()

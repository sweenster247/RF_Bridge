"""Threaded tinySA scan worker for the PySide6 UI."""

import time

import serial
from PySide6.QtCore import QObject, QTimer, Signal, Slot

from .config import BAUD, TINYSA_SERIAL_TIMEOUT_SECONDS, TINYSA_SERIAL_WRITE_TIMEOUT_SECONDS, TINYSA_STARTUP_SETTLE_SECONDS
from .scanner import read_frequencies_mhz, read_scan_dbm
from .tinysa import send_command, wake_console
from .utils import clean_tinysa_version


class ScanWorker(QObject):
    """Own the serial connection and polling timer inside a QThread."""

    connected = Signal(str, str, list)       # port, version, freqs_mhz
    scan_ready = Signal(list)                # dbm values
    disconnected = Signal()
    reconnecting = Signal(str)
    error = Signal(str)
    log = Signal(str)

    def __init__(self, port, refresh_seconds, baud=BAUD, debug_serial=False):
        super().__init__()
        self.port = port
        self.refresh_seconds = refresh_seconds
        self.baud = baud
        self.debug_serial = debug_serial
        self.ser = None
        self.timer = None
        self.freqs_mhz = []
        self.running = False
        self._stopped_emitted = False
        self.reconnect_attempted = False

    def _close_serial(self):
        if self.ser is not None:
            try:
                if self.ser.is_open:
                    self.ser.close()
            except Exception:
                pass
            self.ser = None

    def _open_and_initialize(self, emit_connected=True):
        self._debug(
            f"[serial] Opening {self.port} @ {self.baud}; "
            f"timeout={TINYSA_SERIAL_TIMEOUT_SECONDS}; write_timeout={TINYSA_SERIAL_WRITE_TIMEOUT_SECONDS}"
        )
        self.ser = serial.Serial(
            self.port,
            self.baud,
            timeout=TINYSA_SERIAL_TIMEOUT_SECONDS,
            write_timeout=TINYSA_SERIAL_WRITE_TIMEOUT_SECONDS,
        )
        self._debug(f"[serial] Open successful; is_open={self.ser.is_open}")
        self.log.emit(f"Waiting {TINYSA_STARTUP_SETTLE_SECONDS:g}s for tinySA console…")
        time.sleep(TINYSA_STARTUP_SETTLE_SECONDS)

        self.log.emit("Waking tinySA console…")
        wake_console(self.ser, debug_log=self._debug)

        version_output = send_command(self.ser, "version", debug_log=self._debug).strip()
        version = clean_tinysa_version(version_output)
        if version_output:
            self._debug(f"[serial] version parsed={version!r}")
        else:
            self._debug("[serial] version response was empty")

        self.log.emit("Reading tinySA frequency range…")
        self.freqs_mhz = read_frequencies_mhz(self.ser, debug_log=self._debug)
        self._debug(f"[serial] parsed frequency points={len(self.freqs_mhz)}")

        if emit_connected:
            self.connected.emit(self.port, version, self.freqs_mhz)
        self.log.emit(f"Connected to {self.port}")

    def _attempt_single_reconnect(self, reason):
        if self.reconnect_attempted or not self.running:
            return False

        self.reconnect_attempted = True
        notice = (
            "tinySA stopped responding. Attempting one automatic reconnect; "
            "RF Bridge will remain open."
        )
        self.reconnecting.emit(notice)
        self.log.emit(notice)
        self._debug(f"[serial] reconnect reason={reason!r}")

        try:
            self._close_serial()
            time.sleep(1.0)
            self._open_and_initialize(emit_connected=True)
            self.log.emit("tinySA reconnect successful; scanning resumed")
            return True
        except Exception as exc:
            self._debug(f"[serial] reconnect failed: {exc}")
            self.error.emit(
                "tinySA stopped responding and RF Bridge could not reconnect. "
                "Power-cycle or restart the tinySA, then restart RF Bridge."
            )
            self.stop()
            return False

    @Slot()
    def start(self):
        try:
            self._open_and_initialize(emit_connected=True)

            self.running = True
            self.reconnect_attempted = False

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
            dbm = read_scan_dbm(self.ser, debug_log=self._debug)
            self._debug(f"[serial] parsed scan points={len(dbm)}")
            self.reconnect_attempted = False
        except Exception as exc:
            # During app shutdown the serial port may already be closing. Do not
            # surface that as a user-facing scan error. For a live device fault,
            # try one automatic reconnect before escalating to the UI.
            if self.running and self._attempt_single_reconnect(str(exc)):
                return
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

        self._close_serial()

        self._stopped_emitted = True
        self.disconnected.emit()

    def _debug(self, message):
        if self.debug_serial:
            self.log.emit(message)
            try:
                print(message, flush=True)
            except Exception:
                pass

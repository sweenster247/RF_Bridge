"""Threaded tinySA scan worker for the PySide6 UI."""

import threading
import time

import serial
from serial.tools import list_ports
from PySide6.QtCore import QObject, QTimer, Signal, Slot

from .config import (
    BAUD,
    TINYSA_CONNECT_ATTEMPTS,
    TINYSA_CONNECT_RETRY_SECONDS,
    TINYSA_RECONNECT_POLL_SECONDS,
    TINYSA_RECONNECT_WINDOW_SECONDS,
    TINYSA_SERIAL_TIMEOUT_SECONDS,
    TINYSA_SERIAL_WRITE_TIMEOUT_SECONDS,
    TINYSA_STARTUP_SETTLE_SECONDS,
)
from .scan_profile import ACQUISITION_SCANRAW, ScanProfile, recommended_refresh_seconds
from .scanner import configure_scan_profile, read_frequencies_mhz, read_scan_dbm, read_scanraw_profile
from .tinysa import send_command, wake_console
from .utils import clean_tinysa_version


class ScanWorker(QObject):
    """Own the serial connection and polling timer inside a QThread."""

    connected = Signal(str, str, list)       # port, version, freqs_mhz
    scan_ready = Signal(list)                # dbm values
    disconnected = Signal()
    reconnecting = Signal(str)
    retuned = Signal(str, float, float, list)
    retune_failed = Signal(str)
    scan_progress = Signal(int, int, str)
    scan_timing = Signal(float, float)
    error = Signal(str)
    log = Signal(str)

    def __init__(self, port, refresh_seconds, baud=BAUD, debug_serial=False, scan_profile=None):
        super().__init__()
        self.port = port
        self.refresh_seconds = refresh_seconds
        self.baud = baud
        self.debug_serial = debug_serial
        self.scan_profile = scan_profile or ScanProfile()
        self.ser = None
        self.timer = None
        self.freqs_mhz = []
        self.running = False
        self.paused = False
        self._stopped_emitted = False
        self._stop_requested = threading.Event()
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

        configure_scan_profile(self.ser, self.scan_profile, debug_log=self._debug)

        if self.scan_profile.acquisition_mode == ACQUISITION_SCANRAW:
            self.freqs_mhz = self.scan_profile.frequency_axis_mhz()
            self.log.emit(f"Using high-resolution USB scan: {self.scan_profile.summary()}")
            self._debug(f"[serial] generated scanraw frequency points={len(self.freqs_mhz)}")
        else:
            self.log.emit("Reading tinySA frequency range…")
            self.freqs_mhz = read_frequencies_mhz(self.ser, debug_log=self._debug)
            self._debug(f"[serial] parsed frequency points={len(self.freqs_mhz)}")

        if emit_connected:
            self.connected.emit(self.port, version, self.freqs_mhz)
        self.log.emit(f"Connected to {self.port}")

    def _open_and_initialize_with_retries(self, emit_connected=True):
        last_error = None
        for attempt in range(1, TINYSA_CONNECT_ATTEMPTS + 1):
            if self._stop_requested.is_set():
                raise serial.SerialException("tinySA connect canceled")
            try:
                self._open_and_initialize(emit_connected=emit_connected)
                return
            except Exception as exc:
                last_error = exc
                self._debug(f"[serial] initialize attempt {attempt} failed: {exc}")
                self._close_serial()
                if attempt >= TINYSA_CONNECT_ATTEMPTS:
                    break
                self.log.emit(
                    "tinySA console was not ready; retrying "
                    f"({attempt + 1}/{TINYSA_CONNECT_ATTEMPTS})"
                )
                time.sleep(TINYSA_CONNECT_RETRY_SECONDS)
        raise last_error or serial.SerialException("tinySA did not initialize")

    def _available_ports(self):
        try:
            return list(list_ports.comports())
        except Exception:
            return []

    def _port_still_available(self):
        ports = self._available_ports()
        if not ports:
            return False
        return any(port.device == self.port for port in ports)

    def _select_reconnect_port(self):
        # Prefer the original selected port, but if macOS re-enumerates the
        # tinySA under a new /dev/cu.* name, fall back to a likely tinySA port.
        if self._port_still_available():
            return self.port

        ports = self._available_ports()
        if not ports:
            return None

        likely = []
        for port in ports:
            combined = " ".join(
                str(value or "")
                for value in (
                    port.device,
                    port.description,
                    port.manufacturer,
                    getattr(port, "product", ""),
                )
            ).lower()
            if "tinysa" in combined or "usb" in combined or "modem" in combined:
                score = 0
                if "tinysa" in combined:
                    score -= 20
                if "/dev/cu." in port.device.lower():
                    score -= 10
                if "usb" in combined or "modem" in combined:
                    score -= 5
                likely.append((score, port.device))
        likely.sort()
        return likely[0][1] if likely else None

    def _serial_looks_open(self):
        return self.ser is not None and getattr(self.ser, "is_open", False)

    def _attempt_single_reconnect(self, reason):
        if self.reconnect_attempted or not self.running:
            return False

        self.reconnect_attempted = True
        notice = (
            "tinySA stopped responding. Waiting for USB hub/dock reconnect; "
            "RF Bridge will remain open."
        )
        self.reconnecting.emit(notice)
        self.log.emit(notice)
        self._debug(f"[serial] reconnect reason={reason!r}")

        try:
            self._close_serial()

            reconnect_port = None
            # USB serial devices can disappear briefly or return under a new
            # /dev/cu.* path. Hubs/docks can take longer to settle than a direct
            # cable, so poll for a bounded window before declaring failure.
            deadline = time.monotonic() + TINYSA_RECONNECT_WINDOW_SECONDS
            while time.monotonic() < deadline and not self._stop_requested.is_set():
                reconnect_port = self._select_reconnect_port()
                if reconnect_port:
                    break
                time.sleep(TINYSA_RECONNECT_POLL_SECONDS)

            if not reconnect_port:
                raise serial.SerialException("tinySA serial port did not reappear")

            if reconnect_port != self.port:
                self.log.emit(f"tinySA reappeared as {reconnect_port}; reconnecting")
                self.port = reconnect_port

            self._open_and_initialize_with_retries(emit_connected=True)
            self.log.emit("tinySA reconnect successful; scanning resumed")
            return True
        except Exception as exc:
            self._debug(f"[serial] reconnect failed: {exc}")
            self.error.emit(
                "tinySA stopped responding and RF Bridge could not reconnect. "
                "If it is on a USB-C/Thunderbolt hub or dock, unplug/replug the hub-side cable "
                "or power-cycle the tinySA, then click Connect again."
            )
            self.stop()
            return False

    def _frequency_range_matches(self, freqs_mhz, low_mhz, high_mhz):
        if not freqs_mhz:
            return False
        observed_low = min(freqs_mhz)
        observed_high = max(freqs_mhz)
        tolerance_mhz = max(0.5, abs(high_mhz - low_mhz) * 0.015)
        return (
            abs(observed_low - low_mhz) <= tolerance_mhz
            and abs(observed_high - high_mhz) <= tolerance_mhz
        )

    def _retune_command_candidates(self, low_hz, high_hz):
        points = len(self.freqs_mhz) if self.freqs_mhz else 450
        return [
            [f"sweep {low_hz} {high_hz}"],
            [f"sweep {low_hz} {high_hz} {points}"],
            [f"start {low_hz}", f"stop {high_hz}"],
            [f"sweep start {low_hz}", f"sweep stop {high_hz}"],
        ]

    def _emit_scanraw_progress(self, current, total):
        if total <= 0:
            percent = 0
        else:
            percent = int(round((current / total) * 100))
        self.scan_progress.emit(
            max(0, min(percent, 100)),
            int(self.scan_profile.points),
            "High-res tinySA scan"
        )

    @Slot()
    def start(self):
        try:
            self._stop_requested.clear()
            self._open_and_initialize_with_retries(emit_connected=True)

            self.running = True
            self.reconnect_attempted = False

            self.timer = QTimer(self)
            self.timer.timeout.connect(self.poll)
            self.timer.start(int(self.refresh_seconds * 1000))
            self.poll()

        except Exception as exc:
            self.error.emit(str(exc))
            self.stop()

    @Slot(str, float, float)
    def retune_range(self, label, low_mhz, high_mhz):
        if not self.running or self.ser is None:
            self.retune_failed.emit("Connect a tinySA before retuning its frequency range.")
            return
        if high_mhz <= low_mhz:
            self.retune_failed.emit("Retune range high frequency must be greater than low frequency.")
            return

        timer_was_active = False
        if self.timer is not None:
            try:
                timer_was_active = self.timer.isActive()
                self.timer.stop()
            except Exception:
                timer_was_active = False

        low_hz = int(round(float(low_mhz) * 1_000_000))
        high_hz = int(round(float(high_mhz) * 1_000_000))
        self.log.emit(
            f"Retuning tinySA to {label}: {low_mhz:.3f}–{high_mhz:.3f} MHz"
        )

        try:
            if not self._serial_looks_open():
                raise serial.SerialException("tinySA serial port is no longer open")

            wake_console(self.ser, debug_log=self._debug)
            last_observed = None

            for commands in self._retune_command_candidates(low_hz, high_hz):
                self._debug(f"[serial] Retune candidate commands={commands!r}")
                for command in commands:
                    send_command(
                        self.ser,
                        command,
                        delay_seconds=0.2,
                        response_window_seconds=1.5,
                        debug_log=self._debug,
                    )
                send_command(
                    self.ser,
                    "refresh",
                    delay_seconds=0.2,
                    response_window_seconds=1.0,
                    debug_log=self._debug,
                )
                time.sleep(0.35)
                freqs_mhz = read_frequencies_mhz(self.ser, debug_log=self._debug)
                if freqs_mhz:
                    last_observed = (min(freqs_mhz), max(freqs_mhz), len(freqs_mhz))
                    self._debug(
                        "[serial] Retune observed frequency range="
                        f"{last_observed[0]:.3f}–{last_observed[1]:.3f} MHz "
                        f"({last_observed[2]} points)"
                    )
                if self._frequency_range_matches(freqs_mhz, low_mhz, high_mhz):
                    self.freqs_mhz = freqs_mhz
                    self.reconnect_attempted = False
                    self.retuned.emit(label, float(low_mhz), float(high_mhz), freqs_mhz)
                    self.log.emit(
                        f"tinySA retuned: {min(freqs_mhz):.3f}–{max(freqs_mhz):.3f} MHz"
                    )
                    self.poll()
                    return

            if last_observed:
                observed = (
                    f"Last tinySA range readback was {last_observed[0]:.3f}–"
                    f"{last_observed[1]:.3f} MHz ({last_observed[2]} points)."
                )
            else:
                observed = "RF Bridge could not read a frequency range back from the tinySA."
            self.retune_failed.emit(
                "Retune command was not confirmed by the tinySA. "
                f"Requested {low_mhz:.3f}–{high_mhz:.3f} MHz. {observed}"
            )
        except Exception as exc:
            self.retune_failed.emit(f"Retune failed: {exc}")
        finally:
            if self.running and self.timer is not None and timer_was_active:
                self.timer.start(int(self.refresh_seconds * 1000))

    @Slot(object)
    def set_scan_profile(self, profile):
        if profile is None:
            return
        self.scan_profile = profile
        self.log.emit(f"Scan setup changed: {self.scan_profile.summary()}")
        if not self.running or self.ser is None:
            return

        try:
            configure_scan_profile(self.ser, self.scan_profile, debug_log=self._debug)
            if self.scan_profile.acquisition_mode == ACQUISITION_SCANRAW:
                self.freqs_mhz = self.scan_profile.frequency_axis_mhz()
                self.retuned.emit(
                    self.scan_profile.label,
                    float(self.scan_profile.low_mhz),
                    float(self.scan_profile.high_mhz),
                    self.freqs_mhz,
                )
            else:
                self.freqs_mhz = read_frequencies_mhz(self.ser, debug_log=self._debug)
                self.retuned.emit(
                    self.scan_profile.label,
                    min(self.freqs_mhz),
                    max(self.freqs_mhz),
                    self.freqs_mhz,
                )
            self.poll()
        except Exception as exc:
            self.retune_failed.emit(f"Could not apply scan setup: {exc}")

    @Slot(float)
    def set_refresh_seconds(self, seconds):
        self.refresh_seconds = seconds
        if self.timer is not None and not self.paused:
            self.timer.start(int(seconds * 1000))
        self.log.emit(f"Refresh changed to {seconds:g}s")

    @Slot(bool)
    def set_paused(self, paused):
        self.paused = bool(paused)
        if self.timer is not None:
            if self.paused:
                self.timer.stop()
            else:
                self.timer.start(int(self.refresh_seconds * 1000))
        self.log.emit("Scanning paused" if self.paused else "Scanning resumed")
        if not self.paused:
            self.poll()

    def request_stop(self):
        self._stop_requested.set()
        self.running = False

    @Slot()
    def poll(self):
        if not self.running or self._stop_requested.is_set() or self.paused or self.ser is None:
            return

        try:
            if not self._serial_looks_open():
                raise serial.SerialException("tinySA serial port is no longer open")
            scan_started = time.monotonic()
            if self.scan_profile.acquisition_mode == ACQUISITION_SCANRAW:
                self.scan_progress.emit(0, int(self.scan_profile.points), "Starting high-res tinySA scan")
                dbm = read_scanraw_profile(
                    self.ser,
                    self.scan_profile,
                    progress_callback=self._emit_scanraw_progress,
                    cancel_check=self._stop_requested.is_set,
                    debug_log=self._debug,
                )
                if self._stop_requested.is_set():
                    return
                self.scan_progress.emit(100, int(self.scan_profile.points), "High-res scan complete")
            else:
                dbm = read_scan_dbm(self.ser, debug_log=self._debug)
            scan_seconds = time.monotonic() - scan_started
            recommended_seconds = recommended_refresh_seconds(scan_seconds)
            self.scan_timing.emit(float(scan_seconds), float(recommended_seconds))
            if recommended_seconds > self.refresh_seconds:
                self.refresh_seconds = recommended_seconds
                if self.timer is not None:
                    self.timer.start(int(self.refresh_seconds * 1000))
            self._debug(f"[serial] parsed scan points={len(dbm)}")
            self.reconnect_attempted = False
        except Exception as exc:
            # During app shutdown the serial port may already be closing. Do not
            # surface that as a user-facing scan error. For a live device fault,
            # try one automatic reconnect before escalating to the UI.
            if self.running and not self._stop_requested.is_set():
                recovered = self._attempt_single_reconnect(str(exc))
                if recovered:
                    return
                # _attempt_single_reconnect emits the user-facing failure and
                # stops the worker when reconnect fails. Avoid a second generic
                # scan error that can mask the reconnect message.
                if not self._stopped_emitted:
                    self.error.emit(f"Scan error: {exc}")
                    self.stop()
            return

        if self.running and not self._stop_requested.is_set():
            self.scan_ready.emit(dbm)

    @Slot()
    def stop(self):
        if self._stopped_emitted:
            return

        self.running = False
        self._stop_requested.set()

        if self.timer is not None:
            try:
                self.timer.stop()
            except Exception:
                pass
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

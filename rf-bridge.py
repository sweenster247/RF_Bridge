import argparse
import bisect
import csv
import os
import re
import shutil
import time
from datetime import datetime

import serial
from serial.tools import list_ports

PORT = None
BAUD = 115200
SCAN_INTERVAL_SECONDS = 300
UI_UPDATE_SECONDS = 2


def time_12h():
    return datetime.now().strftime("%I:%M:%S %p").lstrip("0")


def safe_name(text):
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_") or "gig"


def send_command(ser, cmd):
    ser.write((cmd + "\r").encode())
    time.sleep(0.2)
    return ser.read_until(b"ch> ").decode(errors="ignore")


def parse_numbers(output):
    nums = []

    for line in output.splitlines():
        try:
            nums.append(float(line.strip()))
        except ValueError:
            pass

    return nums


def looks_like_tinysa(*values):
    """
    tinySA devices may identify themselves in either the serial `version`
    response or the USB serial metadata exposed by pyserial.

    Accepting both keeps this command-line workflow from depending on
    `ls /dev/tty.*` while still requiring a tinySA-looking header/name.
    """
    combined = " ".join(
        str(value or "")
        for value in values
    ).lower()

    return "tinysa" in combined


def candidate_serial_ports():
    """
    Return likely serial devices with Mac-friendly ordering.

    pyserial handles the platform differences for us, so this works better
    than shelling out to `ls /dev/tty.*`.
    """
    ports = list(list_ports.comports())

    def sort_key(port):
        device = port.device.lower()

        # On macOS, /dev/cu.* is usually the better app-facing serial endpoint.
        cu_preference = 0 if "/dev/cu." in device else 1

        # USB modems/adapters are more likely than Bluetooth console devices.
        usb_preference = 0 if ("usb" in device or "modem" in device) else 1

        return (
            cu_preference,
            usb_preference,
            device,
        )

    return sorted(ports, key=sort_key)


def describe_port(port):
    parts = [port.device]

    if port.description:
        parts.append(port.description)

    if port.manufacturer:
        parts.append(port.manufacturer)

    return " — ".join(parts)


def find_tinysa_port(baud=BAUD, timeout=1.5):
    """
    Find the tinySA serial port.

    First trust pyserial USB metadata, because on macOS the tinySA often
    advertises itself as something like:

        /dev/cu.usbmodem4001 — tinySA4 — tinysa.org

    Only if metadata is inconclusive do we briefly probe ports with the
    tinySA `version` command. This avoids opening the selected tinySA twice
    and causing a temporary macOS "Resource busy" error.
    """
    ports = candidate_serial_ports()

    if not ports:
        raise RuntimeError(
            "No serial ports were found. Is the tinySA plugged in?"
        )

    scanned = []

    # Fast path: metadata already says tinySA. Do not open the port here.
    for port in ports:
        description = describe_port(port)
        scanned.append(description)

        if looks_like_tinysa(
            port.device,
            port.description,
            port.manufacturer,
            port.product,
            description,
        ):
            return port.device, description, scanned

    # Fallback: metadata did not identify it, so probe each port.
    for port in ports:
        device = port.device

        try:
            with serial.Serial(
                device,
                baud,
                timeout=timeout
            ) as ser:
                time.sleep(0.7)
                ser.reset_input_buffer()

                version_output = send_command(
                    ser,
                    "version"
                )

        except (OSError, serial.SerialException):
            continue

        if looks_like_tinysa(version_output):
            header = version_output.strip() or describe_port(port)
            return device, header, scanned

    scanned_text = "\n".join(
        f"  - {item}"
        for item in scanned
    )

    raise RuntimeError(
        "No tinySA was detected from serial port headers.\n"
        "Scanned ports:\n"
        f"{scanned_text}\n\n"
        "Try forcing it with --port /dev/cu.usbmodem4001."
    )


def validate_frequency_list(freqs_mhz):
    if not freqs_mhz:
        raise RuntimeError(
            "The tinySA returned no frequency points. "
            "Make sure a sweep range is configured on the device, then rerun RF Bridge."
        )


def save_wwb_csv(output_dir, gig_slug, freqs_mhz, dbm):
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    filename = os.path.join(
        output_dir,
        f"{gig_slug}_tinysa_scan_{timestamp}.csv"
    )

    latest_filename = os.path.join(
        output_dir,
        "latest_scan.csv"
    )

    with open(filename, "w", newline="\r\n") as file:
        writer = csv.writer(file)

        for f, level in zip(freqs_mhz, dbm):
            writer.writerow([
                f"{f:.6f}",
                f"{level:.2f}"
            ])

    shutil.copyfile(filename, latest_filename)

    print(f"Saved:  {filename}")
    print(f"Latest: {latest_filename}")


def run_headless(ser, output_dir, gig_slug, freqs_mhz):

    while True:

        dbm = parse_numbers(
            send_command(ser, "data 1")
        )

        print("=" * 50)

        print(
            f"Captured {len(dbm)} scan points at "
            f"{time_12h()}"
        )

        save_wwb_csv(
            output_dir,
            gig_slug,
            freqs_mhz,
            dbm
        )

        time.sleep(SCAN_INTERVAL_SECONDS)


def run_ui(ser, output_dir, gig_slug, freqs_mhz):

    import matplotlib.pyplot as plt
    from matplotlib.widgets import Button

    plt.style.use("dark_background")

    state = {
        "peak_enabled": False,
        "peak_hold": None,
        "latest_dbm": [],
        "last_cursor_index": None,
        "last_save_time": 0,
        "peak_mode_index": 0,

        "peak_modes": [
            ("OFF", None),
            ("LATCH", "latch"),
            ("1 min", 60),
            ("5 min", 300),
            ("15 min", 900),
        ],

        "peak_history": [],
    }

    fig = plt.figure(figsize=(20, 10))
    fig.patch.set_facecolor("#111111")

    ax = fig.add_axes([0.045, 0.13, 0.74, 0.78])
    ax.set_facecolor("#181818")

    side_ax = fig.add_axes([0.84, 0.24, 0.14, 0.69])

    side_ax.set_facecolor("#181818")
    side_ax.axis("off")

    button_ax = fig.add_axes([0.84, 0.15, 0.14, 0.05])

    reset_ax = fig.add_axes([0.84, 0.08, 0.14, 0.05])

    try:
        fig.canvas.manager.set_window_title("RF Bridge")
    except Exception:
        pass

    live_line, = ax.plot(
        [],
        [],
        linewidth=1.5,
        color="#00ff99",
        label="Live"
    )

    peak_line, = ax.plot(
        [],
        [],
        linewidth=1.2,
        color="#ff3333",
        alpha=0.95,
        label="Peak Hold",
    )

    ax.axhline(
        y=-85,
        color="#ffaa00",
        linestyle="--",
        linewidth=1,
        alpha=0.7,
        label="-85 dBm",
    )

    ax.axhline(
        y=-60,
        color="#ff00aa",
        linestyle="--",
        linewidth=1,
        alpha=0.7,
        label="-60 dBm",
    )

    ax.set_title(f"RF Bridge - {gig_slug}")

    ax.set_xlabel("Frequency MHz")
    ax.set_ylabel("Amplitude dBm")

    ax.grid(which="major", alpha=0.25)

    ax.legend(
        loc="lower right",
        facecolor="#181818",
        edgecolor="#444444",
    )

    ax.set_xlim(
        min(freqs_mhz),
        max(freqs_mhz)
    )

    start_mhz = min(freqs_mhz)
    stop_mhz = max(freqs_mhz)

    tick_step = 25

    ticks = []
    current = start_mhz

    while current < stop_mhz:
        ticks.append(round(current, 3))
        current += tick_step

    if round(stop_mhz, 3) not in ticks:
        ticks.append(round(stop_mhz, 3))

    ax.set_xticks(ticks)

    ax.set_ylim(-110, -20)

    ax.set_yticks([
        -110,
        -100,
        -90,
        -85,
        -80,
        -70,
        -60,
        -40,
        -20,
    ])

    readout = ax.text(
        0.01,
        0.98,
        "",
        transform=ax.transAxes,
        va="top",
        ha="left",

        bbox=dict(
            facecolor="#222222",
            alpha=0.9,
            edgecolor="#00ff99",
        ),
    )

    vertical_cursor = ax.axvline(
        x=freqs_mhz[0],
        color="#00ff99",
        alpha=0.45,
        linewidth=1,
        visible=False,
    )

    peak_button = Button(
        button_ax,
        "Peak: OFF",
        color="#222222",
        hovercolor="#333333",
    )

    reset_button = Button(
        reset_ax,
        "Reset Peaks",
        color="#222222",
        hovercolor="#333333",
    )

    def nearest_index(freq):

        idx = bisect.bisect_left(
            freqs_mhz,
            freq
        )

        if idx <= 0:
            return 0

        if idx >= len(freqs_mhz):
            return len(freqs_mhz) - 1

        before = idx - 1
        after = idx

        if (
            abs(freqs_mhz[before] - freq)
            <=
            abs(freqs_mhz[after] - freq)
        ):
            return before

        return after

    def update_top_frequencies(dbm):

        median_floor = (
            sorted(dbm)[len(dbm) // 2]
        )

        strongest = sorted(
            zip(freqs_mhz, dbm),
            key=lambda pair: pair[1],
            reverse=True,
        )[:8]

        text = "RF SUMMARY\n"
        text += "══════════════\n\n"

        text += "Median Floor\n"
        text += f"{median_floor:7.2f} dBm\n\n"

        text += "TOP 8 RF HITS\n"
        text += "──────────────\n\n"

        for i, (freq, level) in enumerate(
            strongest,
            start=1
        ):

            text += (
                f"{i}. {freq:9.3f} MHz\n"
                f"   {level:7.2f} dBm\n\n"
            )

        side_ax.clear()

        side_ax.set_facecolor("#181818")
        side_ax.axis("off")

        side_ax.text(
            0.03,
            0.97,
            text,
            va="top",
            ha="left",
            fontsize=14,
            family="monospace",
            color="#eeeeee",
        )

        # Remove old Top 8 markers
        for line in ax.lines[:]:

            if getattr(
                line,
                "_top8_marker",
                False
            ):
                line.remove()

        # Draw new Top 8 markers
        for freq, level in strongest:

            marker = ax.axvline(
                x=freq,
                color="#666666",
                linestyle=":",
                linewidth=0.8,
                alpha=0.45,
                zorder=0,
            )

            marker._top8_marker = True

    def toggle_peak(event):

        state["peak_mode_index"] = (
            state["peak_mode_index"] + 1
        ) % len(state["peak_modes"])

        label, window_seconds = (
            state["peak_modes"][
                state["peak_mode_index"]
            ]
        )

        peak_button.label.set_text(
            f"Peak: {label}"
        )

        if label == "OFF":

            state["peak_enabled"] = False

            state["peak_hold"] = None

            state["peak_history"] = []

            peak_line.set_data([], [])

        else:

            state["peak_enabled"] = True

            if state["latest_dbm"]:

                now = time.time()

                state["peak_history"].append(
                    (
                        now,
                        state["latest_dbm"].copy()
                    )
                )

                state["peak_hold"] = (
                    state["latest_dbm"].copy()
                )

                peak_line.set_data(
                    freqs_mhz,
                    state["peak_hold"]
                )

        fig.canvas.draw_idle()

    def reset_peaks(event):

        state["peak_enabled"] = False

        state["peak_mode_index"] = 0

        state["peak_hold"] = None

        state["peak_history"] = []

        peak_button.label.set_text(
            "Peak: OFF"
        )

        peak_line.set_data([], [])

        fig.canvas.draw_idle()

    peak_button.on_clicked(toggle_peak)

    reset_button.on_clicked(reset_peaks)

    def on_mouse_move(event):

        if (
            event.inaxes != ax
            or event.xdata is None
            or not state["latest_dbm"]
        ):

            if vertical_cursor.get_visible():

                vertical_cursor.set_visible(False)

                readout.set_text("")

                fig.canvas.draw_idle()

            return

        idx = nearest_index(event.xdata)

        if idx == state["last_cursor_index"]:
            return

        state["last_cursor_index"] = idx

        nearest_freq = freqs_mhz[idx]

        nearest_level = (
            state["latest_dbm"][idx]
        )

        if state["peak_hold"]:

            nearest_peak = (
                state["peak_hold"][idx]
            )

            readout.set_text(
                f"{nearest_freq:.6f} MHz\n"
                f"Live: {nearest_level:.2f} dBm\n"
                f"Peak: {nearest_peak:.2f} dBm"
            )

        else:

            readout.set_text(
                f"{nearest_freq:.6f} MHz\n"
                f"Live: {nearest_level:.2f} dBm"
            )

        vertical_cursor.set_xdata(
            [nearest_freq, nearest_freq]
        )

        vertical_cursor.set_visible(True)

        fig.canvas.draw_idle()

    fig.canvas.mpl_connect(
        "motion_notify_event",
        on_mouse_move
    )

    def update_scan():

        dbm = parse_numbers(
            send_command(ser, "data 1")
        )

        if len(dbm) != len(freqs_mhz):

            print(
                f"Warning: frequency/data mismatch: "
                f"{len(freqs_mhz)} freqs, "
                f"{len(dbm)} levels"
            )

            return True

        state["latest_dbm"] = dbm

        state["last_cursor_index"] = None

        if state["peak_enabled"]:

            now = time.time()

            label, window_seconds = (
                state["peak_modes"][
                    state["peak_mode_index"]
                ]
            )

            state["peak_history"].append(
                (
                    now,
                    dbm.copy()
                )
            )

            if window_seconds == "latch":

                if state["peak_hold"] is None:

                    state["peak_hold"] = dbm.copy()

                else:

                    state["peak_hold"] = [
                        max(old, new)

                        for old, new in zip(
                            state["peak_hold"],
                            dbm
                        )
                    ]

            else:

                cutoff = now - window_seconds

                state["peak_history"] = [

                    sample

                    for sample in state["peak_history"]

                    if sample[0] >= cutoff
                ]

                if state["peak_history"]:

                    samples = [

                        sample[1]

                        for sample in state["peak_history"]
                    ]

                    state["peak_hold"] = [

                        max(values)

                        for values in zip(*samples)
                    ]

            if state["peak_hold"]:

                peak_line.set_data(
                    freqs_mhz,
                    state["peak_hold"]
                )

        live_line.set_data(
            freqs_mhz,
            dbm
        )

        update_top_frequencies(dbm)

        ax.set_title(
            f"RF Bridge - "
            f"{gig_slug} - "
            f"{time_12h()}"
        )

        now = time.time()

        if (
            now - state["last_save_time"]
            >= SCAN_INTERVAL_SECONDS
        ):

            print("=" * 50)

            print(
                f"Captured {len(dbm)} scan points at "
                f"{time_12h()}"
            )

            save_wwb_csv(
                output_dir,
                gig_slug,
                freqs_mhz,
                dbm
            )

            state["last_save_time"] = now

        fig.canvas.draw_idle()

        return True

    timer = fig.canvas.new_timer(
        interval=UI_UPDATE_SECONDS * 1000
    )

    timer.add_callback(update_scan)

    timer.start()

    update_scan()

    plt.show(block=True)


def main():

    parser = argparse.ArgumentParser(
        description="TinySA to WWB RF Bridge"
    )

    parser.add_argument(
        "--ui",
        action="store_true",
        help="Show real-time RF graph"
    )

    parser.add_argument(
        "--port",
        default=None,
        help="Manually choose a serial port if auto-detection is not desired"
    )

    parser.add_argument(
        "--list-ports",
        action="store_true",
        help="List detected serial ports and exit"
    )

    args = parser.parse_args()

    if args.list_ports:
        ports = candidate_serial_ports()

        if not ports:
            print("No serial ports found.")
            return

        print("Detected serial ports:")

        for port in ports:
            print(f"  - {describe_port(port)}")

        return

    gig_name = input("Gig name: ")

    gig_slug = safe_name(gig_name)

    output_dir = os.path.join(
        "wwb_scans",
        gig_slug
    )

    os.makedirs(
        output_dir,
        exist_ok=True
    )

    if args.port:
        selected_port = args.port
        version_output = None
        print(f"Using manually selected port: {selected_port}")
    else:
        selected_port, version_output, scanned_ports = find_tinysa_port()

        print("Auto-detected tinySA:")
        print(f"  {selected_port}")

        if version_output:
            print(version_output)

    with serial.Serial(
        selected_port,
        BAUD,
        timeout=2
    ) as ser:

        time.sleep(1)

        if version_output is None:
            version_output = send_command(
                ser,
                "version"
            ).strip()

            print(version_output)

        freqs_hz = parse_numbers(
            send_command(
                ser,
                "frequencies"
            )
        )

        freqs_mhz = [
            f / 1_000_000

            for f in freqs_hz
        ]

        validate_frequency_list(freqs_mhz)

        print(
            f"Serial port: "
            f"{selected_port}"
        )

        print(
            f"Output folder: "
            f"{output_dir}"
        )

        print(
            f"Scan interval: "
            f"{SCAN_INTERVAL_SECONDS} seconds"
        )

        print(
            f"UI refresh: "
            f"{UI_UPDATE_SECONDS} seconds"
        )

        print(
            f"Frequency range: "
            f"{min(freqs_mhz):.3f} MHz - "
            f"{max(freqs_mhz):.3f} MHz"
        )

        print(
            f"UI enabled: "
            f"{args.ui}"
        )

        if args.ui:

            run_ui(
                ser,
                output_dir,
                gig_slug,
                freqs_mhz
            )

        else:

            run_headless(
                ser,
                output_dir,
                gig_slug,
                freqs_mhz
            )


if __name__ == "__main__":
    main()
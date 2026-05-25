"""Matplotlib-based RF Bridge v1.3 UI.

This preserves the v1.2 visual behavior while isolating the UI layer so a
future native app window can replace it cleanly.
"""

import bisect
import time

from .config import SCAN_INTERVAL_SECONDS, UI_UPDATE_SECONDS
from .export import save_wwb_csv
from .tinysa import send_command
from .utils import parse_numbers, time_12h


def run_ui(ser, output_dir, gig_slug, freqs_mhz, ui_update_seconds=UI_UPDATE_SECONDS, selected_port=None):

    import matplotlib.pyplot as plt
    from matplotlib.widgets import Button

    plt.style.use("dark_background")

    refresh_modes = [
        0.5,
        1,
        2,
        5,
        10,
    ]

    refresh_index = min(
        range(len(refresh_modes)),
        key=lambda index: abs(refresh_modes[index] - ui_update_seconds)
    )

    state = {
        "peak_enabled": False,
        "peak_hold": None,
        "latest_dbm": [],
        "last_cursor_index": None,
        "last_save_time": 0,
        "peak_mode_index": 0,
        "refresh_index": refresh_index,
        "refresh_seconds": ui_update_seconds,

        "refresh_modes": refresh_modes,

        "peak_modes": [
            ("OFF", None),
            ("LATCH", "latch"),
            ("1 min", 60),
            ("5 min", 300),
            ("15 min", 900),
        ],

        "peak_history": [],
    }

    fig = plt.figure(figsize=(20, 10), constrained_layout=False)
    fig.patch.set_facecolor("#111111")

    # Fixed normalized layout: wide plot, right summary/control rail, bottom status bar.
    # This scales with the window, but it is intentionally not a fully responsive GUI layout.
    ax = fig.add_axes([0.060, 0.245, 0.715, 0.640])
    ax.set_facecolor("#181818")

    side_ax = fig.add_axes([0.815, 0.470, 0.160, 0.395])
    side_ax.set_facecolor("#111111")
    side_ax.axis("off")

    # Thin visual divider between the plot and the right panel.
    divider_ax = fig.add_axes([0.795, 0.185, 0.0015, 0.700])
    divider_ax.set_facecolor("#777777")
    divider_ax.set_xticks([])
    divider_ax.set_yticks([])

    # Control buttons sit higher and line up under the RF summary.
    button_ax = fig.add_axes([0.815, 0.330, 0.160, 0.055])
    reset_ax = fig.add_axes([0.815, 0.255, 0.160, 0.055])
    refresh_ax = fig.add_axes([0.815, 0.180, 0.160, 0.055])

    # Bottom status strip spans the bottom like an application status bar.
    status_ax = fig.add_axes([0.030, 0.070, 0.945, 0.070])
    status_ax.set_facecolor("#181818")
    status_ax.set_xticks([])
    status_ax.set_yticks([])
    for spine in status_ax.spines.values():
        spine.set_color("#555555")

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

    refresh_button = Button(
        refresh_ax,
        f"Refresh: {state['refresh_seconds']:g}s",
        color="#222222",
        hovercolor="#333333",
    )

    for button in (peak_button, reset_button, refresh_button):
        button.label.set_fontsize(11)
        button.label.set_color("#eeeeee")

    status_text = status_ax.text(
        0.035,
        0.5,
        "",
        va="center",
        ha="left",
        fontsize=11,
        family="monospace",
        color="#eeeeee",
    )

    def update_status(now=None):

        if now is None:
            now = time.time()

        if state["last_save_time"]:
            next_save = max(
                0,
                SCAN_INTERVAL_SECONDS - int(now - state["last_save_time"])
            )
        else:
            next_save = 0

        minutes = next_save // 60
        seconds = next_save % 60

        port_label = selected_port or "auto"

        status_text.set_text(
            f"Scan Folder: {output_dir}   |   "
            f"Latest: latest_scan.csv   |   "
            f"Next Save: {minutes}:{seconds:02d}   |   "
            f"Refresh: {format_seconds(state['refresh_seconds'])}s   |   "
            f"tinySA: {port_label}"
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
        text += "──────────────────────\n\n"

        text += "Median Floor\n"
        text += f"{median_floor:7.2f} dBm\n\n"

        text += "TOP 8 RF HITS\n"
        text += "──────────────────────\n"

        for i, (freq, level) in enumerate(
            strongest,
            start=1
        ):

            text += (
                f"{i}. {freq:9.3f} MHz  {level:7.2f} dBm\n"
            )

        side_ax.clear()

        side_ax.set_facecolor("#111111")
        side_ax.axis("off")

        side_ax.text(
            0.03,
            0.97,
            text,
            va="top",
            ha="left",
            fontsize=12,
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

    timer_state = {
        "timer": None,
    }

    def format_seconds(seconds):

        if float(seconds).is_integer():
            return str(int(seconds))

        return str(seconds)

    def start_scan_timer(seconds):

        if timer_state["timer"] is not None:
            timer_state["timer"].stop()

        timer = fig.canvas.new_timer(
            interval=int(seconds * 1000)
        )

        timer.add_callback(update_scan)

        timer.start()

        timer_state["timer"] = timer

    def set_refresh_interval(seconds):

        state["refresh_seconds"] = seconds

        refresh_button.label.set_text(
            f"Refresh: {format_seconds(seconds)}s"
        )

        start_scan_timer(seconds)

        print(f"UI refresh changed to {seconds} seconds")

        update_status()

        fig.canvas.draw_idle()

    def toggle_refresh(event):

        state["refresh_index"] = (
            state["refresh_index"] + 1
        ) % len(state["refresh_modes"])

        set_refresh_interval(
            state["refresh_modes"][state["refresh_index"]]
        )

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

    refresh_button.on_clicked(toggle_refresh)

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

        update_status(now)

        fig.canvas.draw_idle()

        return True

    start_scan_timer(state["refresh_seconds"])

    update_scan()

    plt.show(block=True)


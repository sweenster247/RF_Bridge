# RF Bridge

TinySA live RF analyzer and WWB CSV exporter for live sound engineers.

Built for fast RF coordination workflows using a TinySA and a MacBook.

---

## Features

* Real-time RF spectrum visualization
* Peak hold modes

  * Latch
  * 1 minute
  * 5 minute
  * 15 minute
* Top 8 strongest RF hits
* Median RF noise floor monitoring
* Frequency cursor readout
* WWB-compatible CSV exports
* Automatic timestamped scan logging
* Dark mode friendly UI
* Lightweight and portable

---

# Hardware Requirements

* TinySA or TinySA Ultra
* USB cable
* MacBook running macOS

---

# Software Requirements

## 1. Install Xcode Command Line Tools

Open Terminal and run:

```bash
xcode-select --install
```

This installs:

* Python support
* Build tools
* USB serial support
* pip

You may need to reboot or reopen Terminal afterward.

---

## 2. Verify Python Installation

Run:

```bash
python3 --version
```

You should see something similar to:

```text
Python 3.x.x
```

---

## 3. Install Dependencies

Install required Python packages:

```bash
pip3 install pyserial matplotlib
```

Dependencies used:

* pyserial
* matplotlib

---

# TinySA Setup

Connect the TinySA via USB.

Find the TinySA serial device:

```bash
ls /dev/tty.*
```

You should see something similar to:

```text
/dev/tty.usbmodem4001
```

Update the script if your port differs:

```python
PORT = "/dev/tty.usbmodem4001"
```

---

# Suggested Sweep Ranges

Example wireless audio coordination sweep:

```text
400 MHz - 600 MHz
```

Suggested workflow:

* Configure sweep range directly on TinySA
* Launch RF Bridge afterward
* RF Bridge automatically adapts to TinySA sweep settings

---

# Running RF Bridge

## Launch UI Mode

```bash
python3 rf_bridge.py --ui
```

---

## Launch Headless CSV Export Mode

```bash
python3 rf_bridge.py
```

---

# CSV Export Behavior

Scans are automatically saved every 5 minutes.

Exports include:

* Timestamped CSV files
* latest_scan.csv shortcut

Example output:

```text
wwb_scans/
└── festival_show/
    ├── latest_scan.csv
    ├── festival_show_tinysa_scan_2026-05-24_22-15-00.csv
    └── festival_show_tinysa_scan_2026-05-24_22-20-00.csv
```

These CSVs can be imported into Wireless Workbench.

---

# UI Features

## Cursor Readout

Hover over the RF graph to display:

* Frequency
* Live RF level
* Peak RF level

---

## Peak Hold Modes

Click the Peak button to cycle through:

* OFF
* LATCH
* 1 min
* 5 min
* 15 min

Reset Peaks clears all stored peak data.

---

## RF Summary Panel

Displays:

* Median noise floor
* Top 8 RF hits
* Live strongest frequencies

---

# Notes

* RF Bridge uses the TinySA as the source of truth
* Frequency ranges automatically follow TinySA sweep settings
* Restart RF Bridge after changing TinySA sweep ranges
* Designed for lightweight field use
* Tested on macOS

---

# Recommended Future Features

Potential future additions:

* Wireless mic frequency overlays
* WWB integration
* Occupied frequency detection
* TV channel shading
* Scan screenshots/export
* Multi-receiver support

---

# Troubleshooting

## “pip3: command not found”

Install Xcode Command Line Tools:

```bash
xcode-select --install
```

---

## No TinySA Found

Verify device path:

```bash
ls /dev/tty.*
```

Update:

```python
PORT = "/dev/tty.usbmodemXXXX"
```

---

## Frequency/Data Mismatch Warning

Usually caused by:

* Changing TinySA sweep settings while RF Bridge is running
* USB disconnects
* TinySA not actively scanning

Restart RF Bridge after sweep changes.

---

# License

MIT License

Use freely, modify freely, share freely.

---

# Credits

Created by Cody Sweeny

Built for live sound engineers, RF coordinators, and anyone tired of every useful tool becoming a subscription.

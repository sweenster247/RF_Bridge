# RF Bridge

RF Bridge is a lightweight Python utility that connects a tinySA spectrum analyzer to Shure Wireless Workbench (WWB) by exporting live RF scans as WWB-compatible CSV files.

Designed for live sound engineers, RF coordinators, churches, theaters, and festival workflows that want fast RF visibility without expensive proprietary hardware.

---

## Features

* Live RF scanning from tinySA
* WWB-compatible CSV exports
* Real-time matplotlib RF visualization UI
* Peak hold modes

  * OFF
  * LATCH
  * 1 minute
  * 5 minute
  * 15 minute
* Top 8 RF hit summary panel
* Automatic scan saving
* Automatic tinySA serial port detection
* Manual serial port override support
* Headless mode support for unattended scanning

---

# Requirements

## Hardware

* tinySA or tinySA Ultra
* USB cable
* Mac, Linux, or Windows system with Python 3

---

# macOS Setup

## 1. Install Python 3

Modern macOS versions usually include Python, but installing the latest version is recommended.

Install from:

https://www.python.org/downloads/

Verify installation:

```bash
python3 --version
```

---

## 2. Install Dependencies

Install required Python packages:

```bash
pip3 install pyserial matplotlib
```

---

# Usage

## Start with UI

```bash
python3 rf-bridge.py --ui
```

You will be prompted for a gig name.

Example:

```text
Gig name: Blues Fest
```

---

## Headless Mode

Run without the live graph UI:

```bash
python3 rf-bridge.py
```

---

# Automatic tinySA Detection

RF Bridge automatically scans serial devices and selects the first device identified as a tinySA.

Example:

```text
Auto-detected tinySA:
  /dev/cu.usbmodem4001
```

No more:

```bash
ls /dev/tty.*
```

Like civilized people.

---

# Manual Port Override

If automatic detection fails:

```bash
python3 rf-bridge.py --port /dev/cu.usbmodem4001 --ui
```

---

# List Serial Ports

```bash
python3 rf-bridge.py --list-ports
```

Example:

```text
Detected serial ports:
  - /dev/cu.usbmodem4001 — tinySA4 — tinysa.org
```

---

# Output Files

Scans are automatically written to:

```text
wwb_scans/<gig_name>/
```

Example:

```text
wwb_scans/blues_fest/
```

Each scan produces:

* timestamped historical CSV
* latest_scan.csv

---

# WWB Import

Inside Wireless Workbench:

1. Open Frequency Coordination
2. Import scan data
3. Select `latest_scan.csv`

---

# Notes

* tinySA sweep range must already be configured on the device
* RF Bridge does not currently configure sweep ranges remotely
* `/dev/cu.*` devices are preferred automatically on macOS
* If another serial monitor is open, the port may appear busy

---

# Known Issues

* macOS may briefly lock the serial port after reconnecting the tinySA
* Extremely large sweep ranges may reduce UI responsiveness
* WWB import formatting may vary slightly between WWB versions

---

# Planned Features

* Native WWB integration
* Scan averaging
* Waterfall display
* Occupancy analysis
* Native packaged macOS app
* Multi-device scanning

---

# License

MIT License

---

Built for live sound engineers, RF coordinators, and anyone tired of everything being a subscription these days.

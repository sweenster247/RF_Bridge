# RF Bridge v1.1 Release Notes

## Added

### Automatic tinySA Detection

RF Bridge now automatically discovers connected tinySA devices using serial metadata and USB descriptors.

No more manual `ls /dev/tty.*` workflows.

### Manual Port Override

Added support for:

```bash
--port <device>
```

Example:

```bash
python3 rf-bridge.py --port /dev/cu.usbmodem4001 --ui
```

### Serial Port Listing

Added:

```bash
--list-ports
```

to display available serial devices.

### Frequency Validation

Added protection against empty frequency responses from tinySA.

This prevents crashes caused by:

* invalid sweep configuration
* disconnected devices
* incomplete serial responses

### Improved macOS Support

* prioritizes `/dev/cu.*` devices automatically
* improved USB serial sorting logic
* more reliable tinySA detection

---

## Fixed

* Fixed auto-detection failures when tinySA metadata was present but serial headers were unavailable
* Fixed temporary serial port lock behavior
* Fixed missing helper function regression
* Fixed empty frequency list crash (`min() arg is an empty sequence`)

---

## Internal Improvements

* Cleaner serial probing logic
* Better runtime error messaging
* Improved device scanning workflow
* More defensive validation around serial data handling

---

## Upgrade Notes

Dependencies unchanged:

```bash
pip3 install pyserial matplotlib
```

No configuration changes required.

---

## Thanks

Special thanks to everyone stubborn enough to debug serial ports on macOS.

# Changelog

## v1.6.2
- Changed packaged-app gig/session prompt to start empty instead of prefilled
- Added packaged-app storage location prompt after gig/session name
- Default app storage location remains `~/Documents/RF Bridge`
- Scans continue saving under `wwb_scans/<gig>` inside the selected storage location
- Preserved script/CLI behavior

## v1.6.1
- Fixed packaged macOS app launch behavior after gig/session prompt
- Deferred tinySA auto-detection until after the main app window is visible
- Changed packaged app default output path to `~/Documents/RF Bridge/wwb_scans/<gig>`
- Preserved existing script/CLI behavior

## v1.6
- Added packaged-app launch mode for macOS builds
- Double-clicked PyInstaller app bundles now launch the desktop UI by default
- Added GUI gig/session name prompt for app launches
- Added `--app` mode for testing packaged-app behavior from Terminal
- Added `--gig` argument to bypass interactive gig-name prompts
- Added `--output-dir` argument for custom scan output locations
- Improved PyInstaller spec for PySide6, pyqtgraph, and pyserial bundling
- Added macOS bundle metadata to the PyInstaller spec
- Updated build script for one-command unsigned app bundle creation
- Bumped internal package version to `1.6.0`

## v1.5.1
- Fixed Qt thread-safety issue in the PySide6 UI
- Routed worker-thread updates through Qt signals/queued UI calls
- Prevented UI log updates from running directly inside the scan worker thread
- Improved refresh/disconnect/shutdown behavior across thread boundaries
- Resolved repeated `QBasicTimer::start: Timers cannot be started from another thread` warnings
- Resolved crash risk from `QObject: Cannot create children for a parent that is in a different thread`
- Preserved v1.5 connection panel, threaded scanning, Freeze Trace, persistent settings, and packaging prep

## v1.5
- Moved PySide6 UI scanning into a background QThread
- Added tinySA connection panel with port dropdown
- Added Refresh Ports, Connect, and Disconnect controls
- Added device status, version, and sweep range display
- Added in-app event log pane
- Added Freeze Trace mode for inspecting RF activity without stopping scans
- Added persistent UI settings with QSettings
- Preserved headless CSV capture mode
- Preserved WWB CSV export and latest_scan.csv behavior
- Added PyInstaller packaging prep for future macOS app builds

## v1.4
- Replaced Matplotlib UI with PySide6 application window
- Replaced Matplotlib plotting with pyqtgraph
- Preserved live RF graph behavior
- Preserved peak hold modes
- Preserved refresh interval cycling
- Preserved RF summary and Top 8 RF hits panel
- Preserved bottom status bar
- Preserved WWB CSV export behavior
- Updated dependencies for PySide6 and pyqtgraph
- Prepared UI layer for future packaged Mac app builds

## v1.3
- Refactored RF Bridge into modular app-ready architecture
- Split tinySA serial handling into dedicated module
- Split WWB CSV export logic into dedicated module
- Split scan loop/state handling into dedicated module
- Split UI into dedicated module
- Added centralized app entrypoint structure
- Preserved existing CLI behavior and arguments
- Prepared project structure for future packaged app builds
- Improved long-term maintainability and IDE workflow

## v1.2
- Redesigned wide UI
- Added live refresh controls
- Added bottom status bar
- Improved RF summary layout
- Fixed refresh timer behavior

## v1.1
- Added automatic tinySA detection
- Added serial port listing
- Added manual port overrides
- Fixed empty frequency scan crashes

## v1.0
- Initial release
- tinySA → WWB CSV bridge
- Real-time RF graph
- Peak hold modes

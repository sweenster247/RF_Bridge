# Changelog

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

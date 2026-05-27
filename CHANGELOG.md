# Changelog

## v1.9.6
- Added a graph right-click menu for creating Mic Plot markers at the clicked frequency with a name-only prompt.
- Added graph right-click removal for visible Mic Plot markers using `Remove Marker: Name`.
- Staggered nearby Mic Plot marker labels vertically so close frequencies remain readable.
- Expanded the fixed RF amplitude range to `-110 dBm` through `-10 dBm`.
- Reinforced graph Y-axis locking and 10 dB major tick spacing so high-amplitude traces do not shift the view.

## v1.9.5.25
- Reduced live graph redraw work by keeping capture overlay curves alive between scans.
- Reused Top RF Hit marker lines instead of recreating them every refresh.
- Made Top RF Hit selection lighter while preserving the existing summary display.
- Trimmed peak-hold history in place for timed peak modes.
- Updated `latest_scan.csv` with an atomic replace instead of copying the timestamped capture file.
- Restored GitHub dependency maintenance files in the repository.
- Updated version metadata and README for v1.9.5.25.

## v1.9.5.24
- Matched the top-right connection panel width to the RF Summary panel.
- Added right-click refresh options with a custom refresh interval dialog.
- Added optional automatic live trace overlays from Preferences, capped to the latest six auto traces and without creating extra CSV files.
- Snapped hover readout and Top RF Hits frequency display to 0.005 MHz increments.
- Added a little extra spacing between right-side control icons and labels.
- Updated version metadata and README for v1.9.5.24.

## v1.9.5.23

- Replaced emoji-style sidebar controls with clean SVG icons.
- Added icon assets for Peak, Reset, Refresh, Freeze, and Return to Live.
- Kept the compact v1.9.5.22 right-sidebar layout while improving visual polish.

## v1.9.5.23
- Refined the right RF summary sidebar to reduce Top 8 clipping/crowding.
- Widened the RF panel slightly and converted Peak/Reset plus Refresh/Freeze into compact side-by-side control rows.
- Reduced sidebar button and hover inspector height, shortened labels, and added lightweight icons for a cleaner utility-app feel.

## v1.9.5.21
- Batched UI polish for connection stability, Demo Mode layout stability, larger sidebar navigation text, and a shorter bottom status bar.
- Added live/disconnected device state to the lower left sidebar.
- Added a right-click Peak menu while keeping the existing left-click peak toggle.

## v1.9.5.20
- Shortened RF plot hover readout text and rounded hover frequencies to three decimals so the live readout fits in the UI.

## v1.9.5.19
- Added low/high frequency range labels directly on the RF plot.

## v1.9.5.18
- Stabilized the main window layout so connection, device, and status text changes do not resize the app window.

## v1.9.5.17
- Cleaned up tinySA disconnect handling so unplugged/unavailable devices switch the connection UI back to reconnect state.
- Reduced repeated frequency/data mismatch log spam and disconnect after repeated mismatched scans so the range can be refreshed.

## v1.9.5.16
- Added extra noise, transient spikes, and subtle floor movement to Demo Mode.
- Refined the macOS app icon source so the RF Bridge artwork fills more of the icon without the extra bordered frame.

## v1.9.5.15
- Added visual-only Demo Mode to the device dropdown.
- Demo Mode simulates RF graph activity without writing CSV files or touching `wwb_scans`.

## v1.9.5.14
- Cleaned raw tinySA console echo/prompt text from the device label.
- Simplified the connection card action row so connected state shows one Disconnect action.
- Removed the dark background block behind the connection status indicator.

## v1.9.5.13
- Cleaned up the tinySA connection panel layout.
- Added an in-panel notice when the tinySA serial console does not return data.
- Simplified the RF plot left-axis label to `dBm` to avoid clipped axis lettering.

## v1.9.5.12
- Added a conservative tinySA wake sequence before the first `version` command.
- The wake sequence sends blank lines, `resume`, `release`, and `refresh` with bounded reads.

## v1.9.5.11
- Removed blocking `read_until()` and serial flush calls from tinySA command handling.
- Added a serial write timeout so USB serial stalls fail fast instead of freezing the app.
- tinySA commands now use bounded diagnostic-style reads for CR, LF, and CRLF endings.

## v1.9.5.10
- Added a tinySA command fallback that tries the diagnostic read-window strategy when the prompt read returns no bytes.
- The fallback also tries CR, LF, and CRLF command endings to match the standalone diagnostic helper.

## v1.9.5.9
- Fixed a UI auto-connect regression where `debug_serial` was not stored on the main window.
- This prevented the scan worker from starting after tinySA auto-detection.

## v1.9.5.8
- Restored the confirmed-working v1.9.4.10 tinySA prompt-based serial read path.
- Kept v1.9.5.7 debug serial TX/RX logging around the restored command flow.
- Bumped package and macOS bundle metadata to 1.9.5.8.

## v1.9.5.7
- Added debug serial logging mode for tinySA troubleshooting
- Added command TX/RX byte counts and response previews
- Added serial open/close lifecycle logging


## v1.9.5.6
- Increased sidebar navigation text size for readability
- Removed missing Sans-serif font reference to avoid Qt font warnings
- Cleaned connection panel label styling for Status, Device, Port, and Range
- Preserved v1.9.5 UI layout and current tinySA behavior

## v1.9.5.6
- Restored the proven v1.9.4.10 tinySA serial command flow.
- Hard-locked tinySA scan reads to `data 1`.
- Removed aggressive startup command retry/fallback behavior that could hang the app or desynchronize the tinySA console.
- Preserved v1.9.5.3 UI/sidebar/layout polish.
- Preserved graph axis/cursor stability and overlay toggle fixes.

## v1.9.5.2
- Refined sidebar branding with a larger clean logo asset
- Moved RF Bridge title and “RF Spectrum Analyzer” subtitle below the logo
- Widened the sidebar so the subtitle no longer truncates
- Reduced dashboard padding so the main RF graph fills more of the available window
- Tightened overlay and connected-device card heights
- Preserved the v1.9.4.10 tinySA connection path and recent axis/cursor fixes


## v1.9.5.1
- Widened sidebar and improved RF Spectrum Analyzer label spacing
- Enlarged sidebar logo and reduced nested-box appearance
- Expanded main content area within the current app border
- Tightened dashboard panel spacing

## v1.9.5
- Refined main application layout with a polished left sidebar and top-left RF Bridge logo treatment
- Reworked the Capture Overlays panel into a cleaner centered card with helper text
- Moved/condensed connected-device controls into a compact top-right panel aligned with the RF Summary column
- Removed visual clutter behind RF Bridge and Capture Overlays labels
- Preserved confirmed-working v1.9.4.10 tinySA connection behavior and v1.9.4.11/v1.9.4.12 UI stability fixes

## v1.9.4.12
- Added a left-side navigation rail for RF Scan, Markers / Mic Plot, Capture Overlays, Preferences, and About / Help
- Moved the connected-device panel to the top-right of the main window
- Recentered and constrained the Capture Overlays panel so it matches the device panel height and no longer leaves awkward empty space
- Centered the empty-overlay state text
- Kept the confirmed-working v1.9.4.10 tinySA connection behavior and v1.9.4.11 axis/cursor/overlay-toggle fixes

## v1.9.4.11
- Fixed graph auto-resize issue when moving the mouse vertically across the plot
- Locked the dBm vertical range during tinySA connect and first live scan
- Locked plot auto-ranging for cursor, threshold, mic marker, and Top 8 guide lines
- Constrained hover readout height so the main window layout remains stable
- Fixed capture overlay show/hide crash when overlays are detoggled
- Overlay toggles now sync without rebuilding/deleting active Qt widgets
- Based on the confirmed-working v1.9.4.10 tinySA connection path

## v1.9.4.10
- Increased tinySA startup settle time before issuing serial commands
- Increased serial read timeout for tinySA4 console responses
- Added startup log message while waiting for tinySA console readiness
- Based on diagnostic results showing tinySA4 responds reliably after a 5 second settle window

## v1.9.4.9
- Added standalone tinySA serial diagnostic helper
- Added raw command capture for version, frequencies, and data reads
- Added CR/LF/CRLF command ending tests for troubleshooting device communication
- No functional UI changes from v1.9.4.8

## v1.9.4.8
- Restored the proven v1.8-style tinySA frequency read path
- Removed aggressive startup pause/resume behavior that could cause empty frequency lists on some tinySA units
- Kept conservative retry handling without blocking the app UI

## v1.9.4.8
- Improved tinySA startup/connect reliability after v1.9.4 overlay/shutdown changes
- Added more tolerant tinySA frequency-range initialization with pause/read/resume retries
- Prevented transient empty frequency reads from showing blocking startup dialogs
- Kept UI open for capture overlays and manual reconnect when tinySA is not ready

## v1.9.4.4
- Fixed app launch failure caused by missing overlay panel Qt widget imports
- Restored command-line `--ui` startup after v1.9.4.3


## v1.9.4.3
- Reduced the connection panel footprint and moved capture overlay controls beside it
- Added top-bar overlay visibility toggles for quick show/hide access
- Expanded Mic Plot / Marker color options
- Quietly retries transient empty scan reads before showing a warning dialog

## v1.9.4.3
- Added profile workflows for multi-gig days
- Added profile import/export using `.rfbridge-profile.json` files
- Added multi-capture overlay loading
- Added overlay show/hide toggles from the Overlays menu
- Added Help/About menu entries
- Added starter WIKI documentation
- Improved startup handling so failed tinySA auto-connect attempts do not block app launch
- Optimized PyInstaller hidden imports/excludes to reduce app bundle creep

## v1.9.3
- Fixed tinySA startup auto-connect regression where the app could report no frequency points before the device was ready
- Added retry handling when reading the tinySA frequency range during connection
- Slightly delayed packaged-app auto-connect so the main window and serial device have time to settle
- Preserved manual Connect/Disconnect behavior

## v1.9.2
- Refined macOS app icon using RF Bridge logo artwork
- Updated build scripts to regenerate `.icns` when icon source changes
- Updated app icon source to use the RF Bridge logo artwork
- Added consolidated `build_release.sh` workflow for app, DMG, and ZIP release artifacts
- Standardized release artifact names as `RF-Bridge-v{version}-macOS-arm64.dmg` and `RF-Bridge-v{version}-macOS-arm64.zip`
- Updated build scripts to read version metadata from `rf_bridge/version.py`
- Improved Mic Plot label placement so marker names remain visible inside the graph
- Added MHz suffix to Mic Plot labels
- Added subtle label background/border for better readability

## v1.9
- Added Tools > Mic Plot… for manually plotting wireless/mic frequencies
- Added persistent named frequency markers
- Added marker visibility toggles
- Added preset marker colors
- Added vertical labeled marker lines on the RF graph
- Markers display across Live, Frozen, and Loaded Capture modes
- Added mic plot helper module for future marker import/export and overlay workflows

## v1.8
- Added File > Open Capture… for saved RF Bridge CSV scans
- Added Loaded Capture mode for offline scan review
- Added Return to Live menu action and side-panel button
- Preserved live scan saving while a loaded capture is displayed
- Added capture-loading helper module for future overlay support
- Updated docs and release notes for capture loading workflow

## v1.7
- Added Preferences window under `RF Bridge > Preferences…`
- Added appearance setting with System, Dark, and Light options
- Added persistent default refresh setting from Preferences
- Added persistent default storage folder setting for future app sessions
- Added app icon source assets
- Added macOS `.icns` generation helper script
- Updated PyInstaller spec to use the RF Bridge app icon
- Added DMG build script using `create-dmg`
- Updated documentation for app bundle and DMG workflows

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

## v1.9.5.3
- Tightened connected-device panel layout and reduced Connect/Disconnect button footprint.
- Expanded main content area and improved sidebar/logo spacing.
- Added more defensive tinySA serial command retries during startup and scan reads.

# RF Bridge v1.6.2

RF Bridge v1.6.2 is a small packaged-app workflow polish release.

## Changes

- Gig/session prompt now starts empty instead of prefilled
- Added a storage location prompt after entering the gig/session name
- Default storage location is `~/Documents/RF Bridge`
- Scan files are saved under `wwb_scans/<gig>` inside the selected storage location
- Existing script/CLI workflow is unchanged

## Default app save path

If you accept the default storage location and enter a gig named `Blues Fest`, scans save to:

```text
~/Documents/RF Bridge/wwb_scans/blues_fest
```

## Build

```bash
./build_app.sh
```

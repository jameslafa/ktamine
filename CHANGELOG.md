# Changelog

## 0.1.1 — 2026-10-17

- "While downloading" now sees downloads in nested folders (up to six levels
  deep), e.g. Free Download Manager's `Downloads/<name>/<host>/`; before, the
  session could end while a download was still running
- "While an app is running…" now lists apps started by a login autostart entry,
  such as Free Download Manager
- The menu item shows the watched folder: "While downloading in ~/Downloads"
- The end notification says "No download activity", since pausing a download
  also ends the session

## 0.1.0 — 2026-10-17

First release.

- Tray icon: left-click to keep the computer awake, click again to let it sleep
- Keep awake indefinitely, for 15 minutes to 8 hours, a custom number of minutes,
  or until a clock time
- Keep awake while an app is running, or while files are downloading into a
  chosen folder
- Default duration for left-click, the shortcut and `--on`
- Reminder notification before a timer ends, with +15 min … +2 hours buttons
- "Allow display to sleep" to keep the computer awake with the screen off
- Optionally end the session when you suspend the computer or lock the screen
- Global shortcut (Meta+Shift+K by default), changeable from the menu
- `--toggle`, `--on` and `--off` command-line options
- Start at login

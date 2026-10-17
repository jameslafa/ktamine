# ktamine

A tiny "keep awake" tray app for KDE Plasma (and other freedesktop desktops),
inspired by Amphetamine on macOS.

- **Left-click** the tray icon (or press Meta+Shift+K) to toggle keep-awake on/off
  for the default duration (indefinitely unless changed in Settings).
- **Right-click** for timers (15 min – 8 h, or custom) and a Settings submenu:
  default duration, end-of-timer reminder, "Allow display to sleep", ending the
  session on suspend or screen lock, "Start at login" and the shortcut.

It uses the `org.freedesktop.PowerManagement.Inhibit` and
`org.freedesktop.ScreenSaver` D-Bus APIs (falling back to `systemd-inhibit`).
Inhibits are tied to the process, so quitting or crashing always releases them.

## Requirements
- Python 3, PyQt6 (`sudo pacman -S python-pyqt6`)

## Run / install
```sh
python3 -m ktamine      # run from the repo
./install.sh            # installs to ~/.local (make sure ~/.local/bin is on PATH)
```

"""System tray UI: on/off toggle, timer presets, settings."""

from pathlib import Path

from PyQt6.QtCore import QSettings, QTimer, QElapsedTimer
from PyQt6.QtGui import QAction, QActionGroup, QIcon
from PyQt6.QtWidgets import QInputDialog, QMenu, QSystemTrayIcon

from . import APP_NAME
from .inhibitor import Inhibitor
from .sleepwatch import SleepWatcher

ICON_DIR = Path(__file__).parent / "icons"
LAUNCHER = Path(__file__).resolve().parent.parent / "bin" / APP_NAME
AUTOSTART_FILE = Path.home() / ".config" / "autostart" / f"{APP_NAME}.desktop"
PRESETS = [("15 minutes", 15), ("30 minutes", 30), ("1 hour", 60),
           ("2 hours", 120), ("4 hours", 240), ("8 hours", 480)]

DESKTOP_ENTRY = f"""[Desktop Entry]
Type=Application
Name=ktamine
Comment=Keep your computer awake
Exec="{LAUNCHER}"
Icon=system-suspend-inhibited
Terminal=false
Categories=Utility;
X-GNOME-Autostart-enabled=true
"""


def _icon(theme_name, fallback):
    return QIcon.fromTheme(theme_name, QIcon(str(ICON_DIR / fallback)))


def _fmt(ms):
    s = max(0, ms // 1000)
    return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}"


class TrayApp:
    def __init__(self):
        self.settings = QSettings(APP_NAME, APP_NAME)
        self.inhibitor = Inhibitor()
        self.icon_on = _icon("system-suspend-inhibited", "active.svg")
        self.icon_off = _icon("system-suspend-uninhibited", "inactive.svg")

        self.duration_ms = None  # None = indefinite
        self.elapsed = QElapsedTimer()
        self.end_timer = QTimer(singleShot=True, timeout=self._expired)
        self.tick = QTimer(interval=1000, timeout=self._refresh)
        self.sleep_watcher = SleepWatcher()
        self.sleep_watcher.going_to_sleep.connect(self._on_manual_sleep)

        self.tray = QSystemTrayIcon(self.icon_off)
        self.tray.activated.connect(self._on_activated)
        self._build_menu()
        self._refresh()
        self.tray.show()

    # --- menu -------------------------------------------------------------
    def _build_menu(self):
        m = self.menu = QMenu()
        self.status = m.addAction("Inactive")
        self.status.setEnabled(False)
        m.addSeparator()

        self.toggle_act = m.addAction("Keep awake")
        self.toggle_act.setCheckable(True)
        self.toggle_act.triggered.connect(lambda on: self.start() if on else self.stop())

        sub = m.addMenu("Keep awake for…")
        for label, minutes in PRESETS:
            sub.addAction(label).triggered.connect(lambda _=False, mn=minutes: self.start(mn))
        sub.addSeparator()
        sub.addAction("Custom…").triggered.connect(self._custom)
        m.addSeparator()

        self.display_act = m.addAction("Allow display to sleep")
        self.display_act.setCheckable(True)
        self.display_act.setChecked(self.settings.value("allow_display_sleep", False, type=bool))
        self.display_act.toggled.connect(self._display_toggled)

        self.end_on_sleep_act = m.addAction("End session when I put the computer to sleep")
        self.end_on_sleep_act.setCheckable(True)
        self.end_on_sleep_act.setChecked(self.settings.value("end_on_manual_sleep", True, type=bool))
        self.end_on_sleep_act.toggled.connect(
            lambda on: self.settings.setValue("end_on_manual_sleep", on))

        self.autostart_act = m.addAction("Start at login")
        self.autostart_act.setCheckable(True)
        self.autostart_act.setChecked(AUTOSTART_FILE.exists())
        self.autostart_act.toggled.connect(self._autostart_toggled)
        m.addSeparator()

        m.addAction(QIcon.fromTheme("application-exit"), "Quit").triggered.connect(self.quit)
        self.tray.setContextMenu(m)

    # --- actions ----------------------------------------------------------
    def start(self, minutes=None):
        if not self.inhibitor.activate(block_screen=not self.display_act.isChecked()):
            self.tray.showMessage(APP_NAME, "Could not inhibit sleep.",
                                  QSystemTrayIcon.MessageIcon.Warning)
            self._refresh()
            return
        self.end_timer.stop()
        self.duration_ms = None
        if minutes:
            self.duration_ms = minutes * 60_000
            self.elapsed.start()
            self.end_timer.start(self.duration_ms)
            self.tick.start()
        else:
            self.tick.stop()
        self._refresh()

    def stop(self):
        self.inhibitor.deactivate()
        self.end_timer.stop()
        self.tick.stop()
        self.duration_ms = None
        self._refresh()

    def _expired(self):
        self.stop()
        self.tray.showMessage(APP_NAME, "Keep-awake ended. Your computer can sleep again.",
                              self.icon_off)

    def _on_manual_sleep(self):
        # Automatic sleep is blocked while active, so a suspend now was user-initiated.
        if self.inhibitor.active and self.end_on_sleep_act.isChecked():
            self.stop()

    def _custom(self):
        minutes, ok = QInputDialog.getInt(None, APP_NAME, "Keep awake for (minutes):",
                                          value=90, min=1, max=24 * 60)
        if ok:
            self.start(minutes)

    def _on_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.stop() if self.inhibitor.active else self.start()

    def _display_toggled(self, allow):
        self.settings.setValue("allow_display_sleep", allow)
        if self.inhibitor.active:
            remaining = self._remaining_ms()
            self.inhibitor.activate(block_screen=not allow)
            if remaining is not None:
                self.duration_ms = remaining
                self.elapsed.start()
                self.end_timer.start(remaining)

    def _autostart_toggled(self, on):
        if on:
            AUTOSTART_FILE.parent.mkdir(parents=True, exist_ok=True)
            AUTOSTART_FILE.write_text(DESKTOP_ENTRY)
        else:
            AUTOSTART_FILE.unlink(missing_ok=True)

    def quit(self):
        self.stop()
        self.tray.hide()
        from PyQt6.QtWidgets import QApplication
        QApplication.quit()

    # --- display ----------------------------------------------------------
    def _remaining_ms(self):
        if self.duration_ms is None:
            return None
        return max(0, self.duration_ms - self.elapsed.elapsed())

    def _refresh(self):
        active = self.inhibitor.active
        remaining = self._remaining_ms()
        if not active:
            text = "Inactive"
        elif remaining is None:
            text = "Active — indefinitely"
        else:
            text = f"Active — {_fmt(remaining)} left"
        self.status.setText(text)
        self.toggle_act.setChecked(active)
        self.tray.setIcon(self.icon_on if active else self.icon_off)
        self.tray.setToolTip(f"{APP_NAME}: {text}")

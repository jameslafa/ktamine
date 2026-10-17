"""System tray UI: on/off toggle, timer presets, settings."""

import shutil
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from PyQt6.QtCore import QDateTime, QElapsedTimer, QLocale, QProcess, QSettings, Qt, QTime, QTimer
from PyQt6.QtGui import QActionGroup, QIcon
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QSystemTrayIcon,
    QTimeEdit,
    QVBoxLayout,
)

from . import APP_NAME, apps, downloads
from .inhibitor import Inhibitor
from .notifier import Notifier
from .sleepwatch import LockWatcher, SleepWatcher

ICON_DIR = Path(__file__).parent / "icons"
LAUNCHER = Path(__file__).resolve().parent.parent / "bin" / APP_NAME
AUTOSTART_FILE = Path.home() / ".config" / "autostart" / f"{APP_NAME}.desktop"
PRESETS = [("15 minutes", 15), ("30 minutes", 30), ("1 hour", 60),
           ("2 hours", 120), ("4 hours", 240), ("8 hours", 480)]
REMIND_CHOICES = [("Off", 0), ("1 minute before", 1), ("5 minutes before", 5),
                  ("10 minutes before", 10), ("15 minutes before", 15)]
EXTEND_CHOICES = [("+15 min", 15), ("+30 min", 30), ("+1 hour", 60), ("+2 hours", 120)]

DESKTOP_ENTRY = f"""[Desktop Entry]
Type=Application
Name=ktamine
Comment=Keep your computer awake
Exec="{LAUNCHER}"
Icon={ICON_DIR / "active.svg"}
Terminal=false
Categories=Utility;
X-GNOME-Autostart-enabled=true
"""


@dataclass
class Condition:
    """Keep awake while `holds()` is true; checked every few seconds."""
    label: str           # "while Firefox is running"
    holds: Callable[[], bool]
    ended: str           # notification once it stops holding
    grace_ms: int = 0    # don't end within this long of starting


def _ms_until(time):
    """Milliseconds from now until the next occurrence of `time` (tomorrow if passed)."""
    now = QDateTime.currentDateTime()
    target = QDateTime(now.date(), time)
    if target <= now:
        target = target.addDays(1)
    return now.msecsTo(target)


def _short_time(dt):
    return QLocale().toString(dt.time(), QLocale.FormatType.ShortFormat)


def _ask_time(initial):
    """Ask for a clock time; returns a QTime or None if cancelled."""
    dlg = QDialog()
    dlg.setWindowTitle(APP_NAME)
    edit = QTimeEdit(initial)
    edit.setDisplayFormat(QLocale().timeFormat(QLocale.FormatType.ShortFormat))
    hint = QLabel()

    def update_hint(t):
        ms = _ms_until(t)
        day = "today" if QDateTime.currentDateTime().addMSecs(ms).date() == \
            QDateTime.currentDateTime().date() else "tomorrow"
        hint.setText(f"{day}, in {ms // 3_600_000} h {ms // 60_000 % 60:02d} min")

    edit.timeChanged.connect(update_hint)
    update_hint(initial)
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                               | QDialogButtonBox.StandardButton.Cancel)
    buttons.accepted.connect(dlg.accept)
    buttons.rejected.connect(dlg.reject)
    layout = QVBoxLayout(dlg)
    layout.addWidget(QLabel("Keep awake until:"))
    layout.addWidget(edit)
    layout.addWidget(hint)
    layout.addWidget(buttons)
    edit.setFocus()
    return edit.time() if dlg.exec() == QDialog.DialogCode.Accepted else None


def _ask_app():
    """Pick one of the running apps; returns (id, name) or None if cancelled."""
    dlg = QDialog()
    dlg.setWindowTitle(APP_NAME)
    dlg.resize(360, 400)
    listing = QListWidget()
    for app_id, name, icon in apps.running_apps():
        item = QListWidgetItem(QIcon.fromTheme(icon) if icon and not icon.startswith("/")
                               else QIcon(icon), name)
        item.setData(Qt.ItemDataRole.UserRole, (app_id, name))
        listing.addItem(item)
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                               | QDialogButtonBox.StandardButton.Cancel)
    ok = buttons.button(QDialogButtonBox.StandardButton.Ok)
    ok.setEnabled(False)
    listing.currentItemChanged.connect(lambda cur, _: ok.setEnabled(cur is not None))
    listing.itemDoubleClicked.connect(dlg.accept)
    buttons.accepted.connect(dlg.accept)
    buttons.rejected.connect(dlg.reject)
    layout = QVBoxLayout(dlg)
    layout.addWidget(QLabel("Keep awake while this app is running:"))
    layout.addWidget(listing)
    layout.addWidget(buttons)
    if dlg.exec() != QDialog.DialogCode.Accepted or listing.currentItem() is None:
        return None
    return listing.currentItem().data(Qt.ItemDataRole.UserRole)


def _icon(name):
    return QIcon(str(ICON_DIR / name))


def _fmt(ms):
    s = max(0, ms // 1000)
    return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}"


class TrayApp:
    def __init__(self):
        self.settings = QSettings(APP_NAME, APP_NAME)
        self.inhibitor = Inhibitor()
        self.icon_on = _icon("active.svg")
        self.icon_off = _icon("inactive.svg")

        self.duration_ms = None  # None = indefinite
        self.elapsed = QElapsedTimer()
        self.end_timer = QTimer(singleShot=True, timeout=self._expired)
        self.tick = QTimer(interval=1000, timeout=self._refresh)
        self.condition = None
        self.condition_age = QElapsedTimer()
        self.condition_timer = QTimer(interval=5000, timeout=self._check_condition)
        self.remind_timer = QTimer(singleShot=True, timeout=self._remind)
        self.notifier = Notifier(ICON_DIR / "active.svg")
        self.notifier.action_invoked.connect(self._on_notification_action)
        self.sleep_watcher = SleepWatcher()
        self.sleep_watcher.going_to_sleep.connect(self._on_manual_sleep)
        self.lock_watcher = LockWatcher()
        self.lock_watcher.locked.connect(self._on_lock)

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
        self.toggle_act.triggered.connect(lambda on: self.start_default() if on else self.stop())

        sub = m.addMenu("Keep awake for…")
        sub.addAction("Indefinitely").triggered.connect(lambda _=False: self.start())
        for label, minutes in PRESETS:
            sub.addAction(label).triggered.connect(lambda _=False, mn=minutes: self.start(mn))
        sub.addSeparator()
        sub.addAction("Custom…").triggered.connect(self._custom)
        sub.addAction("Until a time…").triggered.connect(self._until)
        sub.addAction("While an app is running…").triggered.connect(self._while_app)
        self.while_downloading_act = sub.addAction("")
        self.while_downloading_act.triggered.connect(self._while_downloading)
        m.addSeparator()

        settings = m.addMenu(QIcon.fromTheme("configure"), "Settings")
        self._radio_menu(settings, "Default duration", [("Indefinitely", 0)] + PRESETS,
                         self._default_minutes(), self._default_changed)
        remind = self._radio_menu(settings, "Remind me before a timer ends", REMIND_CHOICES,
                                  self.settings.value("remind_minutes", 5, type=int),
                                  self._remind_changed)
        remind.setEnabled(self.notifier.available())
        settings.addSeparator()

        self.display_act = settings.addAction("Allow display to sleep")
        self.display_act.setCheckable(True)
        self.display_act.setChecked(self.settings.value("allow_display_sleep", False, type=bool))
        self.display_act.toggled.connect(self._display_toggled)

        self.end_on_sleep_act = settings.addAction("End session when I put the computer to sleep")
        self.end_on_sleep_act.setCheckable(True)
        self.end_on_sleep_act.setChecked(
            self.settings.value("end_on_manual_sleep", True, type=bool))
        self.end_on_sleep_act.toggled.connect(
            lambda on: self.settings.setValue("end_on_manual_sleep", on))

        self.end_on_lock_act = settings.addAction("End session when the screen locks")
        self.end_on_lock_act.setCheckable(True)
        self.end_on_lock_act.setChecked(self.settings.value("end_on_lock", False, type=bool))
        self.end_on_lock_act.setEnabled(self.lock_watcher.connected)
        self.end_on_lock_act.toggled.connect(lambda on: self.settings.setValue("end_on_lock", on))

        self.download_dir_act = settings.addAction("")
        self.download_dir_act.triggered.connect(self._choose_download_dir)
        self._show_download_dir()
        settings.addSeparator()

        self.autostart_act = settings.addAction("Start at login")
        self.autostart_act.setCheckable(True)
        self.autostart_act.setChecked(AUTOSTART_FILE.exists())
        self.autostart_act.toggled.connect(self._autostart_toggled)

        if shutil.which("systemsettings"):
            settings.addAction("Change shortcut…").triggered.connect(self._open_shortcut_settings)
        m.addSeparator()

        m.addAction(QIcon.fromTheme("application-exit"), "Quit").triggered.connect(self.quit)
        self.tray.setContextMenu(m)

    @staticmethod
    def _radio_menu(parent, title, choices, current, on_change):
        menu = parent.addMenu(title)
        group = QActionGroup(menu)
        for label, value in choices:
            act = menu.addAction(label)
            act.setCheckable(True)
            act.setChecked(value == current)
            act.triggered.connect(lambda _=False, v=value: on_change(v))
            group.addAction(act)
        return menu

    # --- actions ----------------------------------------------------------
    def start(self, minutes=None, *, ms=None, condition=None):
        """Start a session: indefinite, timed (`minutes` or `ms`) or while `condition` holds."""
        if not self.inhibitor.activate(block_screen=not self.display_act.isChecked()):
            self.tray.showMessage(APP_NAME, "Could not inhibit sleep.",
                                  QSystemTrayIcon.MessageIcon.Warning)
            self._watch(None)
            self._refresh()
            return
        if ms is None and minutes:
            ms = minutes * 60_000
        self._schedule(ms)
        self._watch(condition)
        self._refresh()

    def start_default(self):
        """Start a session for the default duration (left-click, shortcut, --on)."""
        self.start(self._default_minutes() or None)

    def stop(self):
        self.inhibitor.deactivate()
        self._schedule(None)
        self._watch(None)
        self.tick.stop()
        self._refresh()

    def extend(self, minutes):
        remaining = self._remaining_ms()
        if self.inhibitor.active and remaining is not None:
            self._schedule(remaining + minutes * 60_000)
            self._refresh()

    def _schedule(self, ms):
        """(Re)arm the end and reminder timers for `ms` from now; None = indefinite."""
        self.end_timer.stop()
        self.remind_timer.stop()
        self.notifier.close()
        self.duration_ms = ms
        if ms is None:
            self.tick.stop()
            return
        self.elapsed.start()
        self.end_timer.start(ms)
        self.tick.start()
        lead = self.settings.value("remind_minutes", 5, type=int) * 60_000
        if lead and ms > lead:
            self.remind_timer.start(ms - lead)

    def _remind(self):
        minutes = round(self._remaining_ms() / 60_000)
        when = "in 1 minute" if minutes == 1 else f"in {minutes} minutes"
        self.notifier.show("Keep-awake ending soon",
                           f"Your computer will be allowed to sleep {when}.",
                           [(f"extend:{mn}", label) for label, mn in EXTEND_CHOICES])

    def _on_notification_action(self, key):
        if key.startswith("extend:"):
            self.extend(int(key.split(":", 1)[1]))

    def _default_minutes(self):
        return self.settings.value("default_minutes", 0, type=int)  # 0 = indefinitely

    def _default_changed(self, minutes):
        self.settings.setValue("default_minutes", minutes)
        self._refresh()

    def _remind_changed(self, minutes):
        self.settings.setValue("remind_minutes", minutes)
        remaining = self._remaining_ms()
        if self.inhibitor.active and remaining is not None:
            self._schedule(remaining)

    def _expired(self):
        self.stop()
        self.tray.showMessage(APP_NAME, "Keep-awake ended. Your computer can sleep again.",
                              self.icon_off)

    def _on_manual_sleep(self):
        # Automatic sleep is blocked while active, so a suspend now was user-initiated.
        if self.inhibitor.active and self.end_on_sleep_act.isChecked():
            self.stop()

    def _on_lock(self):
        if self.inhibitor.active and self.end_on_lock_act.isChecked():
            self.stop()

    def _custom(self):
        minutes, ok = QInputDialog.getInt(None, APP_NAME, "Keep awake for (minutes):",
                                          value=90, min=1, max=24 * 60)
        if ok:
            self.start(minutes)

    def _until(self):
        last = self.settings.value("until_time", "")
        initial = QTime.fromString(last, "HH:mm") if last else QTime()
        if not initial.isValid():
            # Next full hour, at least 30 minutes away.
            t = QTime.currentTime().addSecs(30 * 60)
            initial = QTime(t.hour(), 0).addSecs(3600)
        time = _ask_time(initial)
        if time is not None:
            self.settings.setValue("until_time", time.toString("HH:mm"))
            self.start(ms=_ms_until(time))

    def _while_app(self):
        app = _ask_app()
        if app is not None:
            app_id, name = app
            self.start(condition=Condition(
                f"while {name} is running", lambda: app_id in apps.running_ids(),
                f"{name} closed. Keep-awake ended."))

    def _while_downloading(self):
        # The grace period leaves time to start the download after the session.
        folder = self._download_dir()
        self.start(condition=Condition(
            "while downloading", lambda: downloads.in_progress(folder),
            "No download activity. Keep-awake ended.", grace_ms=60_000))

    def _download_dir(self):
        return Path(self.settings.value("download_dir", "") or downloads.download_dir())

    def _show_download_dir(self):
        path = str(self._download_dir()).replace(str(Path.home()), "~", 1)
        self.download_dir_act.setText(f"Watch for downloads in: {path}…")
        self.while_downloading_act.setText(f"While downloading in {path}")

    def _choose_download_dir(self):
        folder = QFileDialog.getExistingDirectory(None, "Folder to watch for downloads",
                                                  str(self._download_dir()))
        if folder:
            # Keep following the system Downloads folder unless another one is picked.
            same = Path(folder) == downloads.download_dir()
            self.settings.setValue("download_dir", "" if same else folder)
            self._show_download_dir()

    def _watch(self, condition):
        self.condition = condition
        if condition:
            self.condition_age.start()
            self.condition_timer.start()
        else:
            self.condition_timer.stop()

    def _check_condition(self):
        c = self.condition
        if self.condition_age.elapsed() < c.grace_ms or c.holds():
            return
        self.stop()
        self.tray.showMessage(APP_NAME, c.ended, self.icon_off)

    def toggle(self):
        self.stop() if self.inhibitor.active else self.start_default()

    def _on_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.toggle()

    def _display_toggled(self, allow):
        self.settings.setValue("allow_display_sleep", allow)
        if self.inhibitor.active:
            remaining = self._remaining_ms()
            self.inhibitor.activate(block_screen=not allow)
            if remaining is not None:
                self._schedule(remaining)

    def _autostart_toggled(self, on):
        if on:
            AUTOSTART_FILE.parent.mkdir(parents=True, exist_ok=True)
            AUTOSTART_FILE.write_text(DESKTOP_ENTRY)
        else:
            AUTOSTART_FILE.unlink(missing_ok=True)

    def _open_shortcut_settings(self):
        # Opens System Settings > Shortcuts with our desktop file's actions selected.
        QProcess.startDetached("systemsettings", ["kcm_keys", "--args", f"{APP_NAME}.desktop"])

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
        elif self.condition:
            text = f"Active — {self.condition.label}"
        elif remaining is None:
            text = "Active — indefinitely"
        else:
            # Round to the nearest minute so timer jitter doesn't flip 17:30 to 17:29.
            end = _short_time(QDateTime.currentDateTime().addMSecs(remaining + 30_000))
            text = f"Active — until {end} ({_fmt(remaining)} left)"
        self.status.setText(text)
        self.toggle_act.setChecked(active)
        default = self._default_minutes()
        label = next((text for text, mn in PRESETS if mn == default), None)
        self.toggle_act.setText(f"Keep awake ({label})" if label and not active else "Keep awake")
        self.tray.setIcon(self.icon_on if active else self.icon_off)
        self.tray.setToolTip(f"{APP_NAME}: {text}")

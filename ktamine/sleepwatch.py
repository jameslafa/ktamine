"""Notice when the system is about to suspend (logind) or the screen gets locked."""

from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot
from PyQt6.QtDBus import QDBusConnection


class SleepWatcher(QObject):
    going_to_sleep = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.connected = QDBusConnection.systemBus().connect(
            "org.freedesktop.login1", "/org/freedesktop/login1",
            "org.freedesktop.login1.Manager", "PrepareForSleep", self._on_prepare)

    @pyqtSlot(bool)
    def _on_prepare(self, starting):
        # Emitted with True before suspend and False after resume.
        if starting:
            self.going_to_sleep.emit()


class LockWatcher(QObject):
    locked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.connected = QDBusConnection.sessionBus().connect(
            "org.freedesktop.ScreenSaver", "/org/freedesktop/ScreenSaver",
            "org.freedesktop.ScreenSaver", "ActiveChanged", self._on_active_changed)

    @pyqtSlot(bool)
    def _on_active_changed(self, active):
        # Emitted with True when the screen locks and False when it unlocks.
        if active:
            self.locked.emit()

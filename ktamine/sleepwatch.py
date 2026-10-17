"""Notice when the system is about to suspend, via logind's PrepareForSleep."""

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

"""Desktop notifications with action buttons, via org.freedesktop.Notifications."""

from PyQt6.QtCore import QMetaType, QObject, pyqtSignal, pyqtSlot
from PyQt6.QtDBus import QDBusArgument, QDBusConnection, QDBusInterface, QDBusMessage

from . import APP_NAME

_SERVICE = "org.freedesktop.Notifications"
_PATH = "/org/freedesktop/Notifications"


def _uint(n):
    return QDBusArgument(n, QMetaType.Type.UInt.value)


class Notifier(QObject):
    action_invoked = pyqtSignal(str)  # action key of our current notification

    def __init__(self, icon_path, parent=None):
        super().__init__(parent)
        self._icon = str(icon_path)
        bus = QDBusConnection.sessionBus()
        self._iface = QDBusInterface(_SERVICE, _PATH, _SERVICE, bus)
        self._id = 0
        bus.connect(_SERVICE, _PATH, _SERVICE, "ActionInvoked", self._on_action)
        bus.connect(_SERVICE, _PATH, _SERVICE, "NotificationClosed", self._on_closed)

    def available(self):
        return self._iface.isValid()

    def show(self, summary, body, actions=()):
        """Show (or replace) our notification. `actions` is [(key, label), ...]."""
        # Action keys/labels must go out as a string array (as), not a variant list (av).
        flat = QDBusArgument([s for pair in actions for s in pair], QMetaType.Type.QStringList.value)
        reply = self._iface.call("Notify", APP_NAME, _uint(self._id), self._icon,
                                 summary, body, flat, {}, 0)
        if reply.type() == QDBusMessage.MessageType.ReplyMessage:
            self._id = reply.arguments()[0]
            return True
        return False

    def close(self):
        if self._id:
            self._iface.call("CloseNotification", _uint(self._id))
            self._id = 0

    @pyqtSlot(QDBusMessage)
    def _on_action(self, msg):
        nid, key = msg.arguments()
        if self._id and nid == self._id:
            self.action_invoked.emit(key)

    @pyqtSlot(QDBusMessage)
    def _on_closed(self, msg):
        if msg.arguments()[0] == self._id:
            self._id = 0

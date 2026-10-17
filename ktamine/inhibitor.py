"""Sleep / screen-lock inhibition via the freedesktop D-Bus APIs.

Inhibits are bound to our D-Bus connection, so they are released
automatically if the process exits or crashes.
"""

import subprocess

from PyQt6.QtCore import QMetaType
from PyQt6.QtDBus import QDBusArgument, QDBusConnection, QDBusInterface, QDBusMessage

from . import APP_NAME

REASON = "Keep awake requested by user"

_PM = ("org.freedesktop.PowerManagement",
       "/org/freedesktop/PowerManagement/Inhibit",
       "org.freedesktop.PowerManagement.Inhibit")
_SS = ("org.freedesktop.ScreenSaver",
       "/org/freedesktop/ScreenSaver",
       "org.freedesktop.ScreenSaver")


class _DBusInhibit:
    def __init__(self, service, path, interface):
        self._iface = QDBusInterface(service, path, interface, QDBusConnection.sessionBus())
        self._cookie = None

    def available(self):
        return self._iface.isValid()

    def acquire(self):
        if self._cookie is not None:
            return True
        reply = self._iface.call("Inhibit", APP_NAME, REASON)
        if reply.type() != QDBusMessage.MessageType.ReplyMessage:
            return False
        self._cookie = reply.arguments()[0]
        return True

    def release(self):
        if self._cookie is not None:
            # Cookie must go out as uint32; a plain Python int is sent as int32.
            self._iface.call("UnInhibit", QDBusArgument(self._cookie, QMetaType.Type.UInt.value))
            self._cookie = None


class Inhibitor:
    def __init__(self):
        self._sleep = _DBusInhibit(*_PM)
        self._screen = _DBusInhibit(*_SS)
        self._proc = None  # systemd-inhibit fallback
        self.active = False

    def activate(self, block_screen=True):
        self.deactivate()
        ok = self._sleep.available() and self._sleep.acquire()
        if block_screen and self._screen.available():
            ok = self._screen.acquire() and ok
        if not ok:
            self._sleep.release()
            self._screen.release()
            ok = self._spawn_fallback(block_screen)
        self.active = ok
        return ok

    def deactivate(self):
        self._sleep.release()
        self._screen.release()
        if self._proc is not None:
            self._proc.terminate()
            self._proc.wait()
            self._proc = None
        self.active = False

    def _spawn_fallback(self, block_screen):
        what = "sleep:idle" if block_screen else "sleep"
        try:
            self._proc = subprocess.Popen(
                ["systemd-inhibit", f"--what={what}", f"--who={APP_NAME}",
                 f"--why={REASON}", "--mode=block", "sleep", "infinity"])
        except OSError:
            return False
        return True

import sys

from PyQt6.QtNetwork import QLocalServer, QLocalSocket
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon

from . import APP_NAME
from .tray import TrayApp


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setDesktopFileName(APP_NAME)
    app.setQuitOnLastWindowClosed(False)

    # Single instance: if another copy is listening, bail out.
    probe = QLocalSocket()
    probe.connectToServer(APP_NAME)
    if probe.waitForConnected(200):
        print(f"{APP_NAME} is already running", file=sys.stderr)
        return 0
    QLocalServer.removeServer(APP_NAME)  # clean stale socket
    server = QLocalServer()
    server.listen(APP_NAME)

    if not QSystemTrayIcon.isSystemTrayAvailable():
        print("No system tray available", file=sys.stderr)
        return 1

    tray = TrayApp()  # noqa: F841 - keep reference alive
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())

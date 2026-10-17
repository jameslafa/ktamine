import argparse
import sys

from PyQt6.QtNetwork import QLocalServer, QLocalSocket
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon

from . import APP_NAME
from .tray import TrayApp

COMMANDS = ("toggle", "on", "off")


def _parse_args():
    p = argparse.ArgumentParser(prog=APP_NAME, description="Keep your computer awake.")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--toggle", dest="command", action="store_const", const="toggle",
                   help="toggle keep-awake in the running instance (starting it if needed)")
    g.add_argument("--on", dest="command", action="store_const", const="on",
                   help="turn keep-awake on")
    g.add_argument("--off", dest="command", action="store_const", const="off",
                   help="turn keep-awake off")
    return p.parse_args()


def _send_to_running(command):
    """Return True if another instance is running (and forward `command` to it)."""
    sock = QLocalSocket()
    sock.connectToServer(APP_NAME)
    if not sock.waitForConnected(200):
        return False
    if command:
        sock.write(f"{command}\n".encode())
        sock.waitForBytesWritten(500)
    sock.disconnectFromServer()
    return True


def _run_command(tray, command):
    if command == "toggle":
        tray.toggle()
    elif command == "on":
        tray.start()
    elif command == "off":
        tray.stop()


def main():
    args = _parse_args()
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setDesktopFileName(APP_NAME)
    app.setQuitOnLastWindowClosed(False)

    # Single instance: if another copy is listening, hand it the command and exit.
    if _send_to_running(args.command):
        if not args.command:
            print(f"{APP_NAME} is already running", file=sys.stderr)
        return 0

    if not QSystemTrayIcon.isSystemTrayAvailable():
        print("No system tray available", file=sys.stderr)
        return 1

    tray = TrayApp()

    QLocalServer.removeServer(APP_NAME)  # clean stale socket
    server = QLocalServer()
    server.listen(APP_NAME)

    def on_connection():
        conn = server.nextPendingConnection()

        def on_ready():
            for line in bytes(conn.readAll()).decode(errors="ignore").split():
                if line in COMMANDS:
                    _run_command(tray, line)

        conn.readyRead.connect(on_ready)
        conn.disconnected.connect(conn.deleteLater)

    server.newConnection.connect(on_connection)

    if args.command:
        _run_command(tray, args.command)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())

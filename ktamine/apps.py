"""Find running desktop apps via the systemd units Plasma launches them in.

Apps started from the launcher, taskbar, autostart or D-Bus activation run in
units under the user's app.slice, named after their desktop file:
app-<id>@<random>.service, app-<id>-<pid>.scope, app-dbus-:1.2-<id>.slice
(dashes inside a name are escaped as \\x2d, an optional launcher prefix may
come before the id).
"""

import os
import re
import shlex
import shutil
from pathlib import Path

from PyQt6.QtCore import QStandardPaths

from . import APP_NAME


def _app_slice():
    try:
        for line in Path("/proc/self/cgroup").read_text().splitlines():
            if line.startswith("0::"):
                parts = line[3:].split("/")
                if "app.slice" in parts:
                    return Path("/sys/fs/cgroup", *parts[:parts.index("app.slice") + 1])
    except OSError:
        pass
    uid = os.getuid()
    return Path(f"/sys/fs/cgroup/user.slice/user-{uid}.slice/user@{uid}.service/app.slice")


def _unescape(s):
    return re.sub(r"\\x([0-9a-fA-F]{2})", lambda m: chr(int(m.group(1), 16)), s)


def _unit_app_id(unit):
    if not unit.startswith("app-"):
        return None
    base, dot, kind = unit[4:].rpartition(".")
    if not dot:
        return None
    if kind == "service":
        return _unescape(base.split("@")[0].split("-")[-1])
    if kind == "scope":
        parts = base.split("-")
        return _unescape(parts[-2] if len(parts) > 1 and parts[-1].isdigit() else parts[-1])
    if kind == "slice":
        # D-Bus activated: app-dbus\x2d:1.2\x2d<bus name>.slice
        return _unescape(base.split("-")[-1]).rpartition("-")[2]
    return None


def _populated(cgroup):
    try:
        return "populated 1" in (cgroup / "cgroup.events").read_text()
    except OSError:
        return False


def running_ids():
    """Desktop-file ids of apps that currently have a live unit."""
    ids = set()
    try:
        entries = list(_app_slice().iterdir())
    except OSError:
        return ids
    for entry in entries:
        app_id = _unit_app_id(entry.name)
        if app_id and entry.is_dir() and _populated(entry):
            ids.add(app_id)
    return ids


def _read_entry(path):
    """Key/values of a desktop file's [Desktop Entry] group."""
    fields, in_entry = {}, False
    try:
        lines = Path(path).read_text(errors="ignore").splitlines()
    except OSError:
        return {}
    for line in lines:
        line = line.strip()
        if line.startswith("["):
            in_entry = line == "[Desktop Entry]"
        elif in_entry and "=" in line:
            key, _, value = line.partition("=")
            fields.setdefault(key.strip(), value.strip())
    return fields


def _exec_binary(fields):
    """Resolved path of the program a desktop entry runs, or None."""
    try:
        args = shlex.split(fields.get("Exec", ""))
    except ValueError:
        return None
    while args and (args[0] == "env" or "=" in args[0]):
        args.pop(0)
    if not args:
        return None
    return os.path.realpath(shutil.which(args[0]) or args[0])


def _menu_entry_running(binary):
    """The app-menu entry that runs `binary`, if any."""
    for folder in QStandardPaths.standardLocations(
            QStandardPaths.StandardLocation.ApplicationsLocation):
        for path in Path(folder).glob("*.desktop"):
            fields = _read_entry(path)
            if fields.get("NoDisplay") != "true" and _exec_binary(fields) == binary:
                return fields
    return None


def _desktop_entry(app_id):
    """(Name, Icon) for an app id, or None if there isn't a desktop file to show."""
    path = QStandardPaths.locate(QStandardPaths.StandardLocation.ApplicationsLocation,
                                 f"{app_id}.desktop")
    fields = _read_entry(path) if path else {}
    if not fields:
        # Started from a login autostart entry, which only lives in an autostart folder.
        for folder in QStandardPaths.standardLocations(
                QStandardPaths.StandardLocation.GenericConfigLocation):
            autostart = Path(folder, "autostart", f"{app_id}.desktop")
            if autostart.is_file():
                fields = _read_entry(autostart)
                # Autostart entries are often bare; prefer the app's menu name and icon.
                binary = _exec_binary(fields)
                fields = (binary and _menu_entry_running(binary)) or fields
                break
    if fields.get("Hidden") == "true" or "Name" not in fields:
        return None
    return fields["Name"], fields.get("Icon", "")


def running_apps():
    """[(id, name, icon)] for running apps that have a desktop file, sorted by name."""
    apps = []
    for app_id in running_ids() - {APP_NAME}:
        entry = _desktop_entry(app_id)
        if entry:
            apps.append((app_id, *entry))
    return sorted(apps, key=lambda a: a[1].lower())

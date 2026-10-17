"""Tell whether something is still downloading into the Downloads folder.

Works for any downloader: a download is "in progress" while a file there, or in
a subfolder up to a few levels deep, is still being written. Known partial-download
files get extra slack so a slow or briefly stalled transfer doesn't count as finished.
"""

import os
import time
from pathlib import Path

from PyQt6.QtCore import QStandardPaths

PARTIAL_SUFFIXES = (".part", ".partial", ".crdownload", ".download", ".fdmdownload",
                    ".aria2", ".!qb", ".opdownload")
WRITE_WINDOW = 60       # s: a file modified this recently is still being written
PARTIAL_WINDOW = 5 * 60  # s: same, for files that look like unfinished downloads


def download_dir():
    return Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DownloadLocation))


def _files(folder, depth=6):
    try:
        with os.scandir(folder) as it:
            for entry in it:
                if entry.name.startswith("."):
                    continue
                if entry.is_file(follow_symlinks=False):
                    yield entry
                elif depth > 1 and entry.is_dir(follow_symlinks=False):
                    yield from _files(entry.path, depth - 1)
    except OSError:
        return


def in_progress(folder=None):
    now = time.time()
    for entry in _files(folder or download_dir()):
        try:
            age = now - entry.stat(follow_symlinks=False).st_mtime
        except OSError:
            continue
        window = PARTIAL_WINDOW if entry.name.lower().endswith(PARTIAL_SUFFIXES) else WRITE_WINDOW
        if age < window:
            return True
    return False

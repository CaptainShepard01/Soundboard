"""
updater.py — Background update checker against GitHub Releases.

Only active when running as a frozen .exe (PyInstaller build).
The update flow:
  1. Background thread calls the GitHub Releases API.
  2. If a newer version exists, a dialog asks the user.
  3. The new .exe is downloaded to %TEMP%.
  4. A small .bat script waits for this process to exit, copies the new exe
     over the current one, and relaunches it.
  5. The app exits cleanly.
"""

import json
import os
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import QApplication, QMessageBox, QProgressDialog

from soundboard import __version__

# The repo whose Releases are checked for updates. Forks should change this.
GITHUB_REPO = "CaptainShepard01/Soundboard"

_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
_HEADERS = {"User-Agent": f"Soundboard/{__version__}"}


def _parse_version(tag: str) -> tuple[int, ...]:
    try:
        return tuple(int(x) for x in tag.lstrip("v").split("."))
    except ValueError:
        return (0,)


class _UpdateChecker(QThread):
    update_available = pyqtSignal(str, str)  # (tag, download_url)

    def run(self) -> None:
        try:
            req = urllib.request.Request(_API_URL, headers=_HEADERS)
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read())

            tag = data.get("tag_name", "")
            if not tag:
                return

            if _parse_version(tag) > _parse_version(__version__):
                for asset in data.get("assets", []):
                    if asset["name"].lower().endswith(".exe"):
                        self.update_available.emit(tag, asset["browser_download_url"])
                        return
        except Exception:
            pass  # non-critical — silently ignore network errors


def _do_update(parent, version: str, download_url: str) -> None:
    reply = QMessageBox.question(
        parent,
        "Update Available",
        f"Version {version} is available (you have {__version__}).\n\n"
        "Download and install now? The app will restart automatically.",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
    )
    if reply != QMessageBox.StandardButton.Yes:
        return

    progress = QProgressDialog("Downloading update…", "Cancel", 0, 0, parent)
    progress.setWindowTitle("Updating Soundboard")
    progress.setWindowModality(Qt.WindowModality.ApplicationModal)
    progress.setMinimumDuration(0)
    progress.setValue(0)
    progress.show()
    QApplication.processEvents()

    tmp_exe = Path(tempfile.gettempdir()) / "Soundboard_update.exe"
    try:
        req = urllib.request.Request(download_url, headers=_HEADERS)
        with urllib.request.urlopen(req, timeout=120) as resp:
            total = int(resp.headers.get("Content-Length", 0))
            progress.setMaximum(total)
            downloaded = 0
            with open(tmp_exe, "wb") as f:
                while True:
                    if progress.wasCanceled():
                        return
                    chunk = resp.read(65536)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total:
                        progress.setValue(downloaded)
                    QApplication.processEvents()
    except Exception as exc:
        progress.close()
        QMessageBox.critical(parent, "Update Failed", f"Download failed:\n{exc}")
        return

    progress.close()

    # Batch script: wait for this process to exit, replace the exe, relaunch.
    current_exe = Path(sys.executable)
    bat = Path(tempfile.gettempdir()) / "soundboard_update.bat"
    bat.write_text(
        "@echo off\n"
        "timeout /t 2 /nobreak > nul\n"
        f'copy /y "{tmp_exe}" "{current_exe}"\n'
        f'start "" "{current_exe}"\n'
        'del "%~0"\n',
        encoding="ascii",
    )

    # Strip PyInstaller's onefile bootloader vars from the child environment.
    # Otherwise the relaunched exe inherits _MEIPASS2/_PYI* (via cmd → start),
    # skips re-extraction, and tries to reuse THIS process's temp dir — which we
    # delete on exit → "Failed to load Python DLL python311.dll" on next launch.
    clean_env = {
        k: v for k, v in os.environ.items()
        if not (k.startswith("_MEIPASS") or k.startswith("_PYI"))
    }

    subprocess.Popen(
        ["cmd", "/c", str(bat)],
        creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW,
        env=clean_env,
    )
    QApplication.quit()


def start_update_check(parent_window) -> "_UpdateChecker | None":
    """Start a background update check. Returns the thread (keep a reference)."""
    if not getattr(sys, "frozen", False):
        return None  # only update frozen .exe builds

    checker = _UpdateChecker()
    checker.update_available.connect(
        lambda v, url: _do_update(parent_window, v, url)
    )
    checker.start()
    return checker

"""
main.py — Entry point for the Soundboard app.

Run with:
    uv run soundboard
Or directly:
    uv run python -m soundboard.main
"""

import sys
from pathlib import Path
from PyQt6.QtCore import QSharedMemory
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon
from soundboard.ui import MainWindow
from soundboard.updater import start_update_check

# Keep a module-level reference so the thread isn't garbage-collected.
_update_checker = None


def _asset_path(relative: str) -> Path:
    """Resolve an asset path for both frozen .exe and dev-mode runs."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / relative
    return Path(__file__).parent.parent / relative


def main() -> None:
    global _update_checker

    app = QApplication(sys.argv)
    app.setApplicationName("Soundboard")
    app.setApplicationDisplayName("Soundboard")

    # Prevent multiple instances
    shared_memory = QSharedMemory("SoundboardAppSharedMemory")
    if shared_memory.attach():
        print("Soundboard is already running.")
        sys.exit(0)
    
    shared_memory.create(1)

    icon_path = _asset_path("assets/icon.png")
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    window = MainWindow()
    window.show()

    _update_checker = start_update_check(window)

    try:
        sys.exit(app.exec())
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    main()

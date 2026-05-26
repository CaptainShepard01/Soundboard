"""
ui.py — PyQt6 soundboard interface.

Layout:
  ┌─────────────────────────────────────────────┐
  │  SOUNDBOARD          [Stop All]  [⚙ Settings]│
  ├─────────────────────────────────────────────┤
  │  Master Volume: ━━━━━━━●━━━  [+ Add Sound]  │
  ├─────────────────────────────────────────────┤
  │  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐       │
  │  │Sound1│ │Sound2│ │Sound3│ │  +  │       │  (grid of SoundButton)
  │  └──────┘ └──────┘ └──────┘ └──────┘       │
  └─────────────────────────────────────────────┘
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt, QPoint, QRect, QSize, QMimeData, pyqtSignal
from PyQt6.QtGui import QKeySequence, QShortcut, QDrag
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLayout,
    QLineEdit,
    QMainWindow,
    QMenu,
    QPushButton,
    QScrollArea,
    QSlider,
    QVBoxLayout,
    QWidget,
    QCheckBox,
    QFrame,
)

from soundboard.audio_engine import AudioEngine, Sound
from soundboard.hotkeys import HotkeyManager
import soundboard.config as config_io


SUPPORTED_FORMATS = "Audio Files (*.mp3 *.wav *.flac *.ogg);;All Files (*)"

# Custom MIME type used for drag-to-reorder of sound buttons (kept distinct from
# file-URL drops so dropping audio files onto the window still adds new sounds).
REORDER_MIME = "application/x-soundboard-reorder"

STYLE = """
QMainWindow, QWidget {
    background-color: #111214;
    color: #e8e8e8;
    font-family: 'Consolas', 'Courier New', monospace;
}
QLabel {
    color: #e8e8e8;
}
QPushButton {
    background-color: #1e2025;
    color: #e8e8e8;
    border: 1px solid #2e3138;
    border-radius: 4px;
    padding: 6px 14px;
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 12px;
}
QPushButton:hover {
    background-color: #2a2d35;
    border-color: #4a9eff;
}
QPushButton:pressed {
    background-color: #4a9eff;
    color: #111214;
}
QPushButton#stopAll {
    background-color: #3a1a1a;
    border-color: #ff4444;
    color: #ff6666;
    font-weight: bold;
}
QPushButton#stopAll:hover {
    background-color: #ff4444;
    color: #111214;
}
QPushButton#soundBtn {
    background-color: #181b22;
    border: 1px solid #2e3138;
    border-radius: 6px;
    font-size: 11px;
    padding: 8px 10px;
    min-width: 110px;
    max-width: 110px;
    min-height: 80px;
    max-height: 80px;
    text-align: left;
}
QPushButton#soundBtn:hover {
    background-color: #1f2430;
    border-color: #4a9eff;
}
QPushButton#soundBtn:pressed {
    background-color: #4a9eff;
    color: #111214;
}
QSlider::groove:horizontal {
    height: 4px;
    background: #2e3138;
    border-radius: 2px;
}
QSlider::handle:horizontal {
    background: #4a9eff;
    width: 14px;
    height: 14px;
    margin: -5px 0;
    border-radius: 7px;
}
QSlider::sub-page:horizontal {
    background: #4a9eff;
    border-radius: 2px;
}
QComboBox {
    background-color: #1e2025;
    border: 1px solid #2e3138;
    border-radius: 4px;
    padding: 4px 8px;
    color: #e8e8e8;
    font-family: 'Consolas', 'Courier New', monospace;
}
QComboBox::drop-down { border: none; }
QComboBox QAbstractItemView {
    background-color: #1e2025;
    border: 1px solid #2e3138;
    selection-background-color: #4a9eff;
}
QLineEdit {
    background-color: #1e2025;
    border: 1px solid #2e3138;
    border-radius: 4px;
    padding: 4px 8px;
    color: #e8e8e8;
    font-family: 'Consolas', 'Courier New', monospace;
}
QScrollArea { border: none; }
QDialog {
    background-color: #111214;
}
QCheckBox { spacing: 6px; }
QCheckBox::indicator {
    width: 14px;
    height: 14px;
    border: 1px solid #2e3138;
    border-radius: 3px;
    background: #1e2025;
}
QCheckBox::indicator:checked {
    background: #4a9eff;
    border-color: #4a9eff;
}
QFrame[frameShape="4"], QFrame[frameShape="5"] {
    color: #2e3138;
}
"""


# ── Flow layout ───────────────────────────────────────────────────────────────

class FlowLayout(QLayout):
    """Wraps child widgets left-to-right, breaking to the next row when needed."""

    def __init__(self, parent=None, spacing: int = 8):
        super().__init__(parent)
        self._items: list = []
        self._spacing = spacing

    def addItem(self, item) -> None:
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int):
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index: int):
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return self._do_layout(QRect(0, 0, width, 0), test_only=True)

    def setGeometry(self, rect: QRect) -> None:
        super().setGeometry(rect)
        self._do_layout(rect, test_only=False)

    def sizeHint(self) -> QSize:
        return self.minimumSize()

    def minimumSize(self) -> QSize:
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        m = self.contentsMargins()
        return size + QSize(m.left() + m.right(), m.top() + m.bottom())

    def _do_layout(self, rect: QRect, *, test_only: bool) -> int:
        m = self.contentsMargins()
        x0 = rect.x() + m.left()
        x, y = x0, rect.y() + m.top()
        right = rect.right() - m.right() + 1  # QRect.right() is inclusive
        row_h = 0
        for item in self._items:
            w, h = item.sizeHint().width(), item.sizeHint().height()
            if x != x0 and x + w > right:
                x, y, row_h = x0, y + row_h + self._spacing, 0
            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), QSize(w, h)))
            x += w + self._spacing
            row_h = max(row_h, h)
        return y + row_h - rect.y() + m.bottom()


# ── Device name helpers ───────────────────────────────────────────────────────

_GENERIC_DEVICES = {
    "microsoft sound mapper - output",
    "primary sound driver",
}


def _clean_device_name(name: str) -> str:
    """Simplify noisy Windows device names to something human-readable."""
    # Bluetooth/driver-path format:
    # "Headset (@System32\drivers\bthhfenum.sys,...;(WH-1000XM5))"
    if "(@system32" in name.lower():
        prefix = re.split(r"\s*\(@", name, maxsplit=1)[0].strip()
        inner = re.search(r"\(([^()]+)\)\s*\)$", name)
        return f"{prefix} ({inner.group(1)})" if inner else prefix
    # Strip empty trailing parens: "Headphones ()"
    return re.sub(r"\s*\(\s*\)\s*$", "", name).strip()


# ── Hotkey capture widget ────────────────────────────────────────────────────

def _qt_key_name(key: Qt.Key, is_numpad: bool) -> str:
    """Map a QKeyEvent key to our hotkey-string format (e.g. 'num1', 'f5', 'a')."""
    K = Qt.Key
    if is_numpad:
        np = {
            K.Key_0: "num0", K.Key_1: "num1", K.Key_2: "num2",
            K.Key_3: "num3", K.Key_4: "num4", K.Key_5: "num5",
            K.Key_6: "num6", K.Key_7: "num7", K.Key_8: "num8",
            K.Key_9: "num9", K.Key_Asterisk: "num*", K.Key_Plus: "num+",
            K.Key_Minus: "num-", K.Key_Slash: "num/", K.Key_Period: "num.",
        }
        if key in np:
            return np[key]
    normal: dict[Qt.Key, str] = {
        K.Key_A: "a", K.Key_B: "b", K.Key_C: "c", K.Key_D: "d",
        K.Key_E: "e", K.Key_F: "f", K.Key_G: "g", K.Key_H: "h",
        K.Key_I: "i", K.Key_J: "j", K.Key_K: "k", K.Key_L: "l",
        K.Key_M: "m", K.Key_N: "n", K.Key_O: "o", K.Key_P: "p",
        K.Key_Q: "q", K.Key_R: "r", K.Key_S: "s", K.Key_T: "t",
        K.Key_U: "u", K.Key_V: "v", K.Key_W: "w", K.Key_X: "x",
        K.Key_Y: "y", K.Key_Z: "z",
        K.Key_0: "0", K.Key_1: "1", K.Key_2: "2", K.Key_3: "3",
        K.Key_4: "4", K.Key_5: "5", K.Key_6: "6", K.Key_7: "7",
        K.Key_8: "8", K.Key_9: "9",
        K.Key_F1:  "f1",  K.Key_F2:  "f2",  K.Key_F3:  "f3",
        K.Key_F4:  "f4",  K.Key_F5:  "f5",  K.Key_F6:  "f6",
        K.Key_F7:  "f7",  K.Key_F8:  "f8",  K.Key_F9:  "f9",
        K.Key_F10: "f10", K.Key_F11: "f11", K.Key_F12: "f12",
        K.Key_Space:    "space",    K.Key_Return:   "enter",
        K.Key_Enter:    "enter",    K.Key_Tab:      "tab",
        K.Key_Delete:   "delete",   K.Key_Insert:   "insert",
        K.Key_Home:     "home",     K.Key_End:      "end",
        K.Key_PageUp:   "pageup",   K.Key_PageDown: "pagedown",
        K.Key_Up:       "up",       K.Key_Down:     "down",
        K.Key_Left:     "left",     K.Key_Right:    "right",
    }
    return normal.get(key, "")


class HotkeyEdit(QLineEdit):
    """Click it, then press any key combo — fills itself with the hotkey string."""

    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self.setPlaceholderText("Click here, then press a key…")

    def keyPressEvent(self, event) -> None:
        key = event.key()
        if key in (Qt.Key.Key_Control, Qt.Key.Key_Shift, Qt.Key.Key_Alt,
                   Qt.Key.Key_Meta, Qt.Key.Key_unknown):
            return  # lone modifier — wait for the main key
        if key in (Qt.Key.Key_Escape, Qt.Key.Key_Backspace):
            self.clear()
            return
        mod = event.modifiers()
        is_numpad = bool(mod & Qt.KeyboardModifier.KeypadModifier)
        parts = []
        if mod & Qt.KeyboardModifier.ControlModifier: parts.append("ctrl")
        if mod & Qt.KeyboardModifier.AltModifier:     parts.append("alt")
        if mod & Qt.KeyboardModifier.ShiftModifier:   parts.append("shift")
        key_str = _qt_key_name(key, is_numpad)
        if key_str:
            parts.append(key_str)
            self.setText("+".join(parts))


# ── Sound Button ──────────────────────────────────────────────────────────────

class _DragHandle(QLabel):
    """Grip strip at the top of a SoundButton. Grabbing it starts a reorder drag."""

    def __init__(self, owner: "SoundButton"):
        super().__init__("⠿⠿⠿")
        self._owner = owner
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFixedHeight(14)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setStyleSheet("color: #555; font-size: 10px;")
        self.setToolTip("Drag to reorder")

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._owner.start_drag()


class SoundButton(QWidget):
    """One cell in the sound grid — play button + volume slider + context menu."""

    edit_requested = pyqtSignal(object)   # emits Sound
    delete_requested = pyqtSignal(object)
    volume_changed = pyqtSignal(object)   # emits Sound after its volume is edited
    # emits (dragged Sound, target Sound, drop_after) when one button is dropped
    # onto another to reorder the grid.
    reorder_requested = pyqtSignal(object, object, bool)

    def __init__(self, sound: Sound, engine: AudioEngine, parent=None):
        super().__init__(parent)
        self.sound = sound
        self.engine = engine
        self.setAcceptDrops(True)   # accept other buttons dropped on us (reorder)
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        self.handle = _DragHandle(self)
        layout.addWidget(self.handle)

        self.btn = QPushButton(self._label(), self)
        self.btn.setObjectName("soundBtn")
        self.btn.clicked.connect(self._play)
        self.btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.btn.customContextMenuRequested.connect(self._context_menu)
        layout.addWidget(self.btn)

        # ── Per-sound volume mixer (mirrors the master-volume slider) ──
        vol_row = QHBoxLayout()
        vol_row.setContentsMargins(2, 0, 2, 0)
        vol_row.setSpacing(4)
        icon = QLabel("🔊")
        self.vol_slider = QSlider(Qt.Orientation.Horizontal)
        self.vol_slider.setRange(0, 100)
        self.vol_slider.setValue(int(self.sound.volume * 100))
        self.vol_slider.valueChanged.connect(self._vol_changed)
        self.vol_pct = QLabel(f"{int(self.sound.volume * 100)}%")
        self.vol_pct.setFixedWidth(34)
        self.vol_pct.setStyleSheet("color: #888; font-size: 10px;")
        vol_row.addWidget(icon)
        vol_row.addWidget(self.vol_slider)
        vol_row.addWidget(self.vol_pct)
        layout.addLayout(vol_row)

    def _label(self) -> str:
        missing = "" if self.sound.path.exists() else "⚠ MISSING\n"
        hotkey_line = f"\n[{self.sound.hotkey}]" if self.sound.hotkey else ""
        return f"{missing}{self.sound.name}{hotkey_line}"

    def _vol_changed(self, value: int) -> None:
        self.sound.volume = value / 100
        self.vol_pct.setText(f"{value}%")
        self.volume_changed.emit(self.sound)

    def refresh(self) -> None:
        self.btn.setText(self._label())
        self.vol_slider.blockSignals(True)
        self.vol_slider.setValue(int(self.sound.volume * 100))
        self.vol_slider.blockSignals(False)
        self.vol_pct.setText(f"{int(self.sound.volume * 100)}%")

    def _play(self) -> None:
        self.engine.stop_all()
        self.engine.play(self.sound)

    def _context_menu(self, pos) -> None:
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #1e2025;
                border: 1px solid #2e3138;
                color: #e8e8e8;
                font-family: 'Consolas', monospace;
            }
            QMenu::item:selected { background-color: #4a9eff; color: #111214; }
        """)
        edit_act = menu.addAction("✏  Edit")
        del_act = menu.addAction("🗑  Remove")
        action = menu.exec(self.btn.mapToGlobal(pos))
        if action == edit_act:
            self.edit_requested.emit(self.sound)
        elif action == del_act:
            self.delete_requested.emit(self.sound)

    # ── Drag-to-reorder ──────────────────────────────────────────────────────

    def start_drag(self) -> None:
        """Begin dragging this button to a new grid position."""
        drag = QDrag(self)
        mime = QMimeData()
        mime.setData(REORDER_MIME, str(id(self.sound)).encode())
        drag.setMimeData(mime)
        drag.setPixmap(self.grab())            # drag a snapshot of the whole cell
        drag.setHotSpot(self.rect().center())
        drag.exec(Qt.DropAction.MoveAction)

    def dragEnterEvent(self, event) -> None:
        # Only react to button-reorder drags; let file-URL drops fall through to
        # the main window (which adds them as new sounds).
        if event.mimeData().hasFormat(REORDER_MIME):
            event.acceptProposedAction()
            self.setStyleSheet("QWidget { background: #2a2d34; border-radius: 6px; }")

    def dragLeaveEvent(self, event) -> None:
        self.setStyleSheet("")

    def dropEvent(self, event) -> None:
        self.setStyleSheet("")
        if not event.mimeData().hasFormat(REORDER_MIME):
            return
        src_id = int(bytes(event.mimeData().data(REORDER_MIME)).decode())
        after = event.position().x() > self.width() / 2
        self.reorder_requested.emit(src_id, self.sound, after)
        event.acceptProposedAction()


# ── Sound Edit Dialog ─────────────────────────────────────────────────────────

class SoundEditDialog(QDialog):
    def __init__(self, sound: Sound, all_sounds: list, parent=None):
        super().__init__(parent)
        self.sound = sound
        self._all_sounds = all_sounds
        self._conflict: Sound | None = None   # sound whose hotkey will be stolen on save
        self.reassigned_from: Sound | None = None
        self.setWindowTitle("Edit Sound")
        self.setMinimumWidth(380)
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        def row(label_text, widget):
            h = QHBoxLayout()
            lbl = QLabel(label_text)
            lbl.setFixedWidth(80)
            h.addWidget(lbl)
            h.addWidget(widget)
            layout.addLayout(h)
            return widget

        self.name_edit = row("Name:", QLineEdit(self.sound.name))

        path_row = QHBoxLayout()
        path_lbl = QLabel("File:")
        path_lbl.setFixedWidth(80)
        self.path_edit = QLineEdit(str(self.sound.path))
        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self._browse)
        path_row.addWidget(path_lbl)
        path_row.addWidget(self.path_edit)
        path_row.addWidget(browse_btn)
        layout.addLayout(path_row)

        self.hotkey_edit = row("Hotkey:", HotkeyEdit(self.sound.hotkey))
        self.hotkey_edit.textChanged.connect(self._clear_conflict)

        self.hotkey_error = QLabel("")
        self.hotkey_error.setStyleSheet("color: #ff6666; font-size: 11px; padding-left: 88px;")
        self.hotkey_error.hide()
        layout.addWidget(self.hotkey_error)

        # Shown only when the typed hotkey clashes with another sound — lets the
        # user steal it instead of having to clear the other sound manually.
        self.reassign_btn = QPushButton("")
        self.reassign_btn.setStyleSheet("margin-left: 88px;")
        self.reassign_btn.clicked.connect(self._do_reassign)
        self.reassign_btn.hide()
        layout.addWidget(self.reassign_btn)

        vol_widget = QWidget()
        vol_h = QHBoxLayout(vol_widget)
        vol_h.setContentsMargins(0, 0, 0, 0)
        self.vol_slider = QSlider(Qt.Orientation.Horizontal)
        self.vol_slider.setRange(0, 100)
        self.vol_slider.setValue(int(self.sound.volume * 100))
        self.vol_pct = QLabel(f"{int(self.sound.volume * 100)}%")
        self.vol_pct.setFixedWidth(40)
        self.vol_slider.valueChanged.connect(lambda v: self.vol_pct.setText(f"{v}%"))
        vol_h.addWidget(self.vol_slider)
        vol_h.addWidget(self.vol_pct)
        row("Volume:", vol_widget)

        self.loop_check = QCheckBox("Loop")
        self.loop_check.setChecked(self.sound.loop)
        layout.addWidget(self.loop_check)

        line = QFrame(); line.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(line)

        btns = QHBoxLayout()
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self._try_accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btns.addStretch()
        btns.addWidget(cancel_btn)
        btns.addWidget(save_btn)
        layout.addLayout(btns)

    def _clear_conflict(self) -> None:
        """Hide the conflict prompt whenever the hotkey field changes."""
        self._conflict = None
        self.hotkey_error.hide()
        self.reassign_btn.hide()
        self.adjustSize()

    def _do_reassign(self) -> None:
        """User confirmed stealing the hotkey from the conflicting sound."""
        self.reassigned_from = self._conflict
        self.accept()

    def _try_accept(self) -> None:
        new_hotkey = self.hotkey_edit.text().strip()
        if new_hotkey and new_hotkey != self.sound.hotkey:
            conflict = next((s for s in self._all_sounds if s is not self.sound and s.hotkey == new_hotkey), None)
            if conflict:
                self._conflict = conflict
                self.hotkey_error.setText(f'Already assigned to "{conflict.name}"')
                self.hotkey_error.show()
                self.reassign_btn.setText(f'Reassign from "{conflict.name}"')
                self.reassign_btn.show()
                self.adjustSize()
                return
        self.hotkey_error.hide()
        self.reassign_btn.hide()
        self.accept()

    def _browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select Audio File", "", SUPPORTED_FORMATS)
        if path:
            self.path_edit.setText(path)
            if not self.name_edit.text():
                self.name_edit.setText(Path(path).stem)

    def apply_to_sound(self) -> None:
        if self.reassigned_from is not None and self.reassigned_from is not self.sound:
            self.reassigned_from.hotkey = ""
        self.sound.name = self.name_edit.text().strip() or self.sound.name
        new_path = Path(self.path_edit.text().strip())
        if new_path != self.sound.path:
            self.sound.path = new_path
            self.sound.invalidate()   # drop cached PCM
        self.sound.hotkey = self.hotkey_edit.text().strip()
        self.sound.volume = self.vol_slider.value() / 100
        self.sound.loop = self.loop_check.isChecked()


# ── Settings Dialog ───────────────────────────────────────────────────────────

class SettingsDialog(QDialog):
    def __init__(self, engine: AudioEngine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.setWindowTitle("Device Settings")
        self.setMinimumWidth(560)
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(14)

        raw_devices = AudioEngine.list_output_devices()
        seen: dict[str, dict] = {}
        for d in raw_devices:
            if d["name"].lower() in _GENERIC_DEVICES:
                continue
            cleaned = _clean_device_name(d["name"])
            seen[cleaned] = {**d, "name": cleaned}  # last (WASAPI) wins
        devices = list(seen.values())
        none_option = {"index": None, "name": "— None —", "channels": 0}
        device_list = [none_option] + devices

        info = QLabel(
            "Monitor device → your headphones (you hear the sound)\n"
            "Discord device → VB-Audio Virtual Cable (Discord hears it)"
        )
        info.setStyleSheet("color: #888; font-size: 11px;")
        info.setWordWrap(True)
        layout.addWidget(info)

        def device_combo(current_idx):
            cb = QComboBox()
            for d in device_list:
                cb.addItem(d["name"], d["index"])
            # select current
            for i, d in enumerate(device_list):
                if d["index"] == current_idx:
                    cb.setCurrentIndex(i)
                    break
            return cb

        def row(label_text, widget):
            h = QHBoxLayout()
            lbl = QLabel(label_text)
            lbl.setFixedWidth(130)
            h.addWidget(lbl)
            h.addWidget(widget)
            layout.addLayout(h)
            return widget

        self.monitor_cb = row("Monitor device:", device_combo(self.engine.monitor_device))
        self.discord_cb = row("Discord device:", device_combo(self.engine.discord_device))

        hint = QLabel("💡 Tip: set Discord input to 'CABLE Output (VB-Audio)' in Discord Settings → Voice")
        hint.setStyleSheet("color: #4a9eff; font-size: 11px;")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        line = QFrame(); line.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(line)

        btns = QHBoxLayout()
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btns.addStretch()
        btns.addWidget(cancel_btn)
        btns.addWidget(save_btn)
        layout.addLayout(btns)

    def apply(self) -> None:
        self.engine.monitor_device = self.monitor_cb.currentData()
        self.engine.discord_device = self.discord_cb.currentData()


# ── Main Window ───────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.engine = AudioEngine()
        self.sounds: list[Sound] = []
        self._sound_widgets: dict[int, SoundButton] = {}  # id(sound) → widget

        self.setWindowTitle("Soundboard")
        self.setMinimumSize(640, 420)
        self.setStyleSheet(STYLE)
        self.setAcceptDrops(True)   # drag audio files onto the window

        self._load_config()
        self._build_ui()
        self._refresh_grid()
        self.hotkey_mgr = HotkeyManager()
        QApplication.instance().installNativeEventFilter(self.hotkey_mgr)
        self._reregister_all_hotkeys()

    # ── Config ─────────────────────────────────────────────────────────────

    def _load_config(self) -> None:
        data = config_io.load()
        self.engine.monitor_device = config_io.resolve_device(data["monitor_device_name"])
        self.engine.discord_device = config_io.resolve_device(data["discord_device_name"])
        self.engine.master_volume = data["master_volume"]
        self.sounds = config_io.sounds_from_config(data)

    def _save_config(self) -> None:
        config_io.save(
            self.sounds,
            self.engine.monitor_device,
            self.engine.discord_device,
            self.engine.master_volume,
        )

    # ── UI construction ────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        # ── Top bar ──
        top = QHBoxLayout()
        title = QLabel("SOUNDBOARD")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #4a9eff; letter-spacing: 3px;")
        top.addWidget(title)
        top.addStretch()

        stop_btn = QPushButton("■ STOP ALL")
        stop_btn.setObjectName("stopAll")
        stop_btn.clicked.connect(self.engine.stop_all)
        stop_btn.setToolTip("Ctrl+Shift+S")
        top.addWidget(stop_btn)

        settings_btn = QPushButton("⚙ Devices")
        settings_btn.clicked.connect(self._open_settings)
        top.addWidget(settings_btn)
        root.addLayout(top)

        # ── Volume bar ──
        vol_row = QHBoxLayout()
        vol_row.addWidget(QLabel("Master Vol:"))
        self.vol_slider = QSlider(Qt.Orientation.Horizontal)
        self.vol_slider.setRange(0, 100)
        self.vol_slider.setValue(int(self.engine.master_volume * 100))
        self.vol_slider.valueChanged.connect(self._master_vol_changed)
        vol_row.addWidget(self.vol_slider)
        self.vol_label = QLabel(f"{int(self.engine.master_volume * 100)}%")
        self.vol_label.setFixedWidth(36)
        vol_row.addWidget(self.vol_label)
        vol_row.addSpacing(20)
        add_btn = QPushButton("+ Add Sound")
        add_btn.clicked.connect(self._add_sound)
        vol_row.addWidget(add_btn)
        root.addLayout(vol_row)

        line = QFrame(); line.setFrameShape(QFrame.Shape.HLine)
        root.addWidget(line)

        # ── Scroll area with flow grid ──
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.grid_container = QWidget()
        self.grid = FlowLayout(self.grid_container, spacing=8)
        self.grid.setContentsMargins(4, 4, 4, 4)
        scroll.setWidget(self.grid_container)
        root.addWidget(scroll, stretch=1)

        # Global stop-all keyboard shortcut (in-window fallback)
        from PyQt6.QtGui import QShortcut
        QShortcut(QKeySequence("Ctrl+Shift+S"), self).activated.connect(self.engine.stop_all)

    # ── Grid management ────────────────────────────────────────────────────

    def _refresh_grid(self) -> None:
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._sound_widgets.clear()

        for sound in self.sounds:
            btn = SoundButton(sound, self.engine, self.grid_container)
            btn.edit_requested.connect(self._edit_sound)
            btn.delete_requested.connect(self._delete_sound)
            btn.volume_changed.connect(lambda _s: self._save_config())
            btn.reorder_requested.connect(self._reorder_sound)
            self.grid.addWidget(btn)
            self._sound_widgets[id(sound)] = btn

    def _reorder_sound(self, src_id: int, dst_sound: Sound, after: bool) -> None:
        """Move the dragged sound to just before/after the drop target."""
        src = next((s for s in self.sounds if id(s) == src_id), None)
        if src is None or src is dst_sound:
            return
        self.sounds.remove(src)
        dst_index = self.sounds.index(dst_sound)
        self.sounds.insert(dst_index + 1 if after else dst_index, src)
        self._refresh_grid()
        self._save_config()

    # ── Sound management ───────────────────────────────────────────────────

    AUDIO_EXTS = {".mp3", ".wav", ".flac", ".ogg"}

    def _add_paths(self, paths: list[Path]) -> None:
        """Add audio files by path, skipping duplicates and non-audio files."""
        existing = {str(s.path) for s in self.sounds}
        added = 0
        for path in paths:
            if path.suffix.lower() not in self.AUDIO_EXTS:
                continue
            if str(path) in existing:
                continue
            self.sounds.append(Sound(name=path.stem, path=path))
            existing.add(str(path))
            added += 1
        if added:
            self._refresh_grid()
            self._save_config()

    def _add_sound(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Add Sounds", "", SUPPORTED_FORMATS
        )
        self._add_paths([Path(p) for p in paths])

    # ── Drag & drop ────────────────────────────────────────────────────────

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        paths = [
            Path(url.toLocalFile())
            for url in event.mimeData().urls()
            if url.isLocalFile()
        ]
        self._add_paths(paths)

    def _edit_sound(self, sound: Sound) -> None:
        old_hotkey = sound.hotkey
        self.hotkey_mgr.unregister_all()
        try:
            dlg = SoundEditDialog(sound, self.sounds, self)
            if dlg.exec() == QDialog.DialogCode.Accepted:
                reassigned_from = dlg.reassigned_from
                dlg.apply_to_sound()
                widget = self._sound_widgets.get(id(sound))
                if widget:
                    widget.refresh()
                if reassigned_from is not None:
                    other = self._sound_widgets.get(id(reassigned_from))
                    if other:
                        other.refresh()
                self._save_config()
        finally:
            self._reregister_all_hotkeys()

    def _delete_sound(self, sound: Sound) -> None:
        if sound.hotkey:
            self.hotkey_mgr.unregister(sound.hotkey)
        self.sounds.remove(sound)
        self._refresh_grid()
        self._save_config()

    # ── Settings ───────────────────────────────────────────────────────────

    def _open_settings(self) -> None:
        dlg = SettingsDialog(self.engine, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            dlg.apply()
            self._save_config()

    # ── Volume ─────────────────────────────────────────────────────────────

    def _master_vol_changed(self, value: int) -> None:
        self.engine.master_volume = value / 100
        self.vol_label.setText(f"{value}%")
        self._save_config()

    # ── Hotkeys ────────────────────────────────────────────────────────────

    def _play_exclusive(self, sound: Sound) -> None:
        self.engine.stop_all()
        self.engine.play(sound)

    def _reregister_all_hotkeys(self) -> None:
        self.hotkey_mgr.unregister_all()
        for sound in self.sounds:
            if sound.hotkey:
                self.hotkey_mgr.register(sound.hotkey, lambda s=sound: self._play_exclusive(s))

    # ── Cleanup ────────────────────────────────────────────────────────────

    def closeEvent(self, event) -> None:
        self.engine.stop_all()
        self.hotkey_mgr.unregister_all()
        QApplication.instance().removeNativeEventFilter(self.hotkey_mgr)
        self._save_config()
        event.accept()

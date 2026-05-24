"""
config.py — Persist soundboard settings to JSON in %APPDATA%\\Soundboard\\config.json.

Persisted:
  - Sound list (name, path, volume, loop, hotkey)
  - Monitor + Discord output devices, stored BY NAME (stable across reboots/replugs)
  - Master volume

Devices are stored by name rather than index because PortAudio indices are
reassigned whenever devices are added/removed. On load we resolve names back to
current indices; if a device is missing, that slot becomes None.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from soundboard.audio_engine import AudioEngine, Sound


CONFIG_DIR = Path.home() / "AppData" / "Roaming" / "Soundboard"
CONFIG_FILE = CONFIG_DIR / "config.json"

_DEFAULTS: dict[str, Any] = {
    "monitor_device_name": None,
    "discord_device_name": None,
    "master_volume": 1.0,
    "sounds": [],
}


def save(
    sounds: list[Sound],
    monitor_device: Optional[int],
    discord_device: Optional[int],
    master_volume: float,
) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    data: dict[str, Any] = {
        "monitor_device_name": AudioEngine.device_name(monitor_device),
        "discord_device_name": AudioEngine.device_name(discord_device),
        "master_volume": master_volume,
        "sounds": [
            {
                "name": s.name,
                "path": str(s.path),
                "volume": s.volume,
                "loop": s.loop,
                "hotkey": s.hotkey,
            }
            for s in sounds
        ],
    }
    tmp = CONFIG_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp.replace(CONFIG_FILE)  # atomic write — never leaves a half-written config


def load() -> dict[str, Any]:
    if not CONFIG_FILE.exists():
        return dict(_DEFAULTS)
    try:
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        return {**_DEFAULTS, **data}
    except Exception:
        return dict(_DEFAULTS)


def resolve_device(name: Optional[str]) -> Optional[int]:
    """Resolve a saved device name back to a current index, or None if gone."""
    if not name:
        return None
    return AudioEngine.find_device_by_name(name)


def sounds_from_config(data: dict[str, Any]) -> list[Sound]:
    sounds: list[Sound] = []
    for entry in data.get("sounds", []):
        path = Path(entry["path"])
        sounds.append(
            Sound(
                name=entry.get("name", path.stem),
                path=path,
                volume=float(entry.get("volume", 1.0)),
                loop=bool(entry.get("loop", False)),
                hotkey=entry.get("hotkey", ""),
            )
        )
    return sounds

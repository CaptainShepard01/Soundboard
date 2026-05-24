"""
audio_engine.py — Dual-output audio playback using miniaudio + sounddevice.

Flow:
  MP3/WAV/FLAC/OGG file
    → miniaudio decodes → raw PCM (numpy float32, 2ch, 44.1kHz)
    → sounddevice plays to BOTH:
        • monitor device  (your headphones — so you hear it)
        • discord device  (VB-Audio Virtual Cable — Discord hears it)

Each play() spawns daemon threads so the UI never blocks. Playback is paced by
sounddevice's blocking write(); a per-playback stop Event lets us interrupt
both one-shot and looping sounds responsively.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import miniaudio
import numpy as np
import sounddevice as sd

SAMPLE_RATE = 44100
CHANNELS = 2
CHUNK = 1024  # frames per write (~23ms) → responsive stop checks


# ── Data model ────────────────────────────────────────────────────────────────

@dataclass
class Sound:
    name: str
    path: Path
    volume: float = 1.0          # 0.0 – 1.0
    loop: bool = False
    hotkey: str = ""             # e.g. "ctrl+1"

    _pcm: Optional[np.ndarray] = field(default=None, repr=False, compare=False)

    def load(self) -> np.ndarray:
        """Decode audio file to a (frames, 2) float32 numpy array. Raises on failure."""
        decoded = miniaudio.decode_file(
            str(self.path),
            output_format=miniaudio.SampleFormat.FLOAT32,
            nchannels=CHANNELS,
            sample_rate=SAMPLE_RATE,
        )
        pcm = np.frombuffer(decoded.samples, dtype=np.float32).reshape(-1, CHANNELS)
        self._pcm = pcm
        return pcm

    @property
    def pcm(self) -> np.ndarray:
        if self._pcm is None:
            self.load()
        return self._pcm

    def invalidate(self) -> None:
        """Drop cached PCM (call after the file path changes)."""
        self._pcm = None


# ── Engine ────────────────────────────────────────────────────────────────────

class AudioEngine:
    """Plays sounds concurrently to up to two output devices simultaneously."""

    def __init__(self) -> None:
        self.monitor_device: Optional[int] = None   # headphones device index
        self.discord_device: Optional[int] = None   # VB-Cable device index
        self.master_volume: float = 1.0
        # Each entry: (stream, stop_event)
        self._active: list[tuple[sd.OutputStream, threading.Event]] = []
        self._lock = threading.Lock()

    # ── Device helpers ─────────────────────────────────────────────────────

    @staticmethod
    def list_output_devices() -> list[dict]:
        devices = []
        for i, dev in enumerate(sd.query_devices()):
            if dev["max_output_channels"] > 0:
                devices.append({
                    "index": i,
                    "name": dev["name"],
                    "channels": dev["max_output_channels"],
                })
        return devices

    @staticmethod
    def find_device_by_name(fragment: str) -> Optional[int]:
        """First output device whose name contains `fragment` (case-insensitive)."""
        if not fragment:
            return None
        frag = fragment.lower()
        for dev in AudioEngine.list_output_devices():
            if frag in dev["name"].lower():
                return dev["index"]
        return None

    @staticmethod
    def device_name(index: Optional[int]) -> Optional[str]:
        """Resolve a device index back to its name (for stable persistence)."""
        if index is None:
            return None
        try:
            return sd.query_devices(index)["name"]
        except Exception:
            return None

    @staticmethod
    def _device_sample_rate(device: Optional[int]) -> int:
        try:
            return int(sd.query_devices(device)["default_samplerate"])
        except Exception:
            return SAMPLE_RATE

    @staticmethod
    def _resample(pcm: np.ndarray, from_rate: int, to_rate: int) -> np.ndarray:
        if from_rate == to_rate:
            return pcm
        n_out = int(round(len(pcm) * to_rate / from_rate))
        t_old = np.arange(len(pcm))
        t_new = np.linspace(0, len(pcm) - 1, n_out)
        return np.column_stack([
            np.interp(t_new, t_old, pcm[:, ch]) for ch in range(pcm.shape[1])
        ]).astype(np.float32)

    # ── Playback ───────────────────────────────────────────────────────────

    def play(self, sound: Sound) -> None:
        """Play `sound` on both configured devices. Non-blocking."""
        try:
            base = sound.pcm
        except Exception as exc:
            print(f"[AudioEngine] Could not load '{sound.name}' ({sound.path}): {exc}")
            return

        pcm = np.clip(base * (sound.volume * self.master_volume), -1.0, 1.0)
        pcm = np.ascontiguousarray(pcm, dtype=np.float32)

        targets: list[Optional[int]] = []
        if self.monitor_device is not None:
            targets.append(self.monitor_device)
        if self.discord_device is not None and self.discord_device != self.monitor_device:
            targets.append(self.discord_device)
        if not targets:
            targets = [None]  # fall back to system default output

        for device in targets:
            stop_event = threading.Event()
            threading.Thread(
                target=self._stream_pcm,
                args=(pcm, device, sound.loop, stop_event),
                daemon=True,
            ).start()

    def _stream_pcm(
        self,
        pcm: np.ndarray,
        device: Optional[int],
        loop: bool,
        stop_event: threading.Event,
    ) -> None:
        stream: Optional[sd.OutputStream] = None
        try:
            device_rate = self._device_sample_rate(device)
            play_pcm = self._resample(pcm, SAMPLE_RATE, device_rate)
            stream = sd.OutputStream(
                samplerate=device_rate,
                channels=CHANNELS,
                dtype="float32",
                device=device,
            )
            stream.start()
            with self._lock:
                self._active.append((stream, stop_event))

            n = len(play_pcm)
            while not stop_event.is_set():
                pos = 0
                while pos < n and not stop_event.is_set():
                    stream.write(play_pcm[pos : pos + CHUNK])
                    pos += CHUNK
                if not loop:
                    break
        except Exception as exc:
            print(f"[AudioEngine] Stream error on device {device}: {exc}")
        finally:
            if stream is not None:
                try:
                    stream.stop()
                    stream.close()
                except Exception:
                    pass
            with self._lock:
                self._active = [(s, e) for (s, e) in self._active if s is not stream]

    def stop_all(self) -> None:
        """Signal every active playback (one-shot and looping) to stop, then abort."""
        with self._lock:
            active = list(self._active)
        for stream, stop_event in active:
            stop_event.set()
            try:
                stream.abort()
            except Exception:
                pass

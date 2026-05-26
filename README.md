# Soundboard

A local, private soundboard for Discord (and any voice app). No subscription, no cloud, no accounts.
Play sounds through your **speakers and Discord at the same time**, triggered by global hotkeys that work even when the app is minimized.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Latest release](https://img.shields.io/github/v/release/CaptainShepard01/Soundboard)](https://github.com/CaptainShepard01/Soundboard/releases/latest)
![Platform: Windows](https://img.shields.io/badge/platform-Windows-blue)

<!-- Tip: add a screenshot of the app here, e.g. ![Soundboard](assets/screenshot.png) -->

## Features

- 🔊 **Dual output** — every sound plays to your headphones *and* into Discord simultaneously
- ⌨️ **Global hotkeys** — trigger sounds from anywhere, even while gaming or with Discord focused
- 🎚️ **Per-sound volume** plus a master volume, independent of each other
- 🔁 **Looping** sounds on/off per button
- 🖱️ **Drag & drop** audio files straight onto the window
- 💾 **Auto-saved** layout, hotkeys, volumes, and device choices
- ⬆️ **Self-updating** — notifies you of new releases and installs them on its own
- 🆓 Runs fully offline; nothing leaves your machine

Supported formats: **MP3, WAV, FLAC, OGG**.

## Contents

- [Install](#install)
- [Setup](#setup)
- [Usage](#usage)
- [Where your data lives](#where-your-data-lives)
- [Updates](#updates)
- [Running from source](#running-from-source)
- [Contributing](#contributing)
- [Author](#author)
- [License](#license)

## Install

Download **Soundboard.exe** from the [**latest release**](https://github.com/CaptainShepard01/Soundboard/releases/latest).
There's no installer — just run it.

> **Windows only.** The app uses Windows audio APIs and global-hotkey registration, so it does not run on macOS or Linux.

## Setup

To route sound into Discord you need a virtual audio cable — a free "virtual microphone" that Discord can listen to.

### 1. Install VB-Audio Virtual Cable (free, one-time)

1. Download from **https://vb-audio.com/Cable/**
2. Run the installer and **restart your PC**
3. You'll now see **CABLE Input** and **CABLE Output** in your Windows audio devices

### 2. Point Discord at the cable (one-time)

1. Discord → **Settings → Voice & Video**
2. Set **Input Device** to `CABLE Output (VB-Audio Virtual Cable)`

That's the only Discord change you need.

### 3. Configure Soundboard (one-time)

1. Run **Soundboard.exe**
2. Click **⚙ Devices** and set:
   - **Monitor device** → your headphones or speakers (so *you* hear the sounds)
   - **Discord device** → `CABLE Input (VB-Audio Virtual Cable)` (so *Discord* hears them)

Your device choices are saved and remembered, even if you replug devices later.

## Usage

### Adding sounds

- Click **+ Add Sound**, or **drag audio files** directly onto the window.
- Right-click any button → **Edit** to change its name, volume, loop setting, or hotkey.
- Drag buttons to reorder them.

### Hotkeys

- Assign a hotkey per sound via right-click → **Edit** (e.g. `ctrl+1`, `f5`, `ctrl+shift+b`).
  These are **global** — they fire even when Soundboard is minimized or another app has focus.
- **Ctrl+Shift+S** stops all playing sounds. (This one works while the Soundboard window is focused.)

### Missing files

If you move or delete a sound file, its button shows **⚠ MISSING**. Right-click → **Edit** → **Browse** to relink it.

## Where your data lives

Everything is auto-saved to:

```
%APPDATA%\Soundboard\config.json
```

This holds your sounds, volumes, hotkeys, loop settings, and your two output devices. Delete it to reset the app.

## Updates

On startup the app checks GitHub for a newer release. If one exists, it asks whether to update; click **Yes** and it downloads, installs, and restarts itself. You never have to manually grab a new `.exe`.

## Running from source

Requires Python ≥ 3.11 and [uv](https://docs.astral.sh/uv/).

```powershell
git clone https://github.com/CaptainShepard01/Soundboard
cd Soundboard
uv sync
uv run soundboard
```

### Build the .exe yourself

```powershell
uv add --dev pyinstaller pillow
uv run pyinstaller --onefile --windowed --name Soundboard `
  --icon assets/icon.png --add-data "assets/icon.png;assets" soundboard/main.py
# Output: dist/Soundboard.exe
```

Pushing a `vMAJOR.MINOR.PATCH` tag triggers the GitHub Actions workflow in
[`.github/workflows/release.yml`](.github/workflows/release.yml), which builds the exe and publishes a release. The helper script `release.sh` automates the version bump, commit, tag, and push.

## Contributing

Issues and pull requests are welcome. For larger changes, please open an issue first to discuss what you'd like to change.

## Author

Made by **Anton Balykov** ([@CaptainShepard01](https://github.com/CaptainShepard01)).

## License

Released under the [MIT License](LICENSE).

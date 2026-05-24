# Soundboard

A local, private Discord soundboard. No subscription, no cloud, no bullshit.  
Play sounds through your speakers **and** Discord at the same time, with global hotkeys.

---

## Download

Go to the [**Releases**](../../releases/latest) page and download **Soundboard.exe**.  
No installation needed — just run it.

---

## Requirements

### VB-Audio Virtual Cable (free, one-time)

This is the "virtual microphone" that lets Discord hear your sounds.

1. Download from **https://vb-audio.com/Cable/**
2. Run the installer and restart your PC
3. That's it — you'll see "CABLE Input" and "CABLE Output" as audio devices

---

## Discord Setup (one-time)

1. Open Discord → **Settings → Voice & Video**
2. Set **Input Device** to `CABLE Output (VB-Audio Virtual Cable)`

That's the only Discord setting you need to change.

---

## First Launch

1. Run **Soundboard.exe**
2. Click **⚙ Devices** and set:
   - **Monitor device** → your headphones or speakers (so *you* hear the sounds)
   - **Discord device** → `CABLE Input (VB-Audio Virtual Cable)` (so Discord hears them)
3. Done — these are saved and remembered.

---

## Adding Sounds

- Click **+ Add Sound**, or **drag audio files** directly onto the window
- Supported formats: MP3, WAV, FLAC, OGG
- Right-click any sound button → **Edit** to change:
  - Name
  - Volume (independent of master volume)
  - Loop on/off
  - Hotkey (e.g. `ctrl+1`, `f5`, `ctrl+shift+b`)

---

## Hotkeys

Hotkeys work even when the soundboard window is minimized or Discord is focused.

- Assign per sound via right-click → **Edit**
- **Ctrl+Shift+S** always stops all playing sounds immediately

---

## Updates

When a new version is released, the app will notify you on startup with a dialog.  
Click **Yes** and it downloads and installs the update automatically — the app restarts on its own.  
You never need to manually download a new `.exe`.

---

## Persistence

Everything is auto-saved to `%APPDATA%\Soundboard\config.json`:  
sounds, volumes, hotkeys, loop settings, and your two output devices.

If you move a sound file, its button shows **⚠ MISSING** — right-click → Edit → Browse to relink it.

---

## Running from Source (developers)

Requires Python ≥ 3.11 and [uv](https://docs.astral.sh/uv/).

```powershell
git clone https://github.com/CaptainShepard01/Soundboard
cd Soundboard
uv sync
uv run soundboard
```

To build the exe yourself:

```powershell
uv add --dev pyinstaller
uv run pyinstaller --onefile --windowed --name Soundboard --icon assets/icon.png --add-data "assets/icon.png;assets" soundboard/main.py
# Output: dist/Soundboard.exe
```

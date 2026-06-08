# EchoPad

Local macOS menubar app: toggle dictation (local parakeet-mlx STT → paste) and
speak-your-selection (MiniMax M3 summary → ElevenLabs TTS).

## Features

- **Dictation (⌥⌘D)** — toggle on, speak, toggle off; your speech is transcribed
  **fully on-device** with [parakeet-mlx](https://github.com/senstella/parakeet-mlx)
  and pasted into the focused app. The clipboard is saved and restored.
- **Speak selection (⌥⌘S)** — grabs your current text selection, summarizes it
  with MiniMax M3, and reads the summary aloud via ElevenLabs TTS. ⌥⌘. stops playback.
- Menubar status: 🎙️ idle · 🔴 recording · ⏳ transcribing · 🔊 speaking.

Dictation needs no network or API key. Only speak-selection calls out (MiniMax + ElevenLabs).

## Setup
1. `brew install portaudio ffmpeg`
2. `python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`
   (If MLX has no wheel for your Python, use Python 3.12: `python3.12 -m venv .venv`.)
3. `export ELEVENLABS_API_KEY=...` (for TTS; MINIMAX_API_KEY is expected to already be set)
4. `cp config.example.toml ~/.config/echopad/config.toml` and edit the voice id.
5. `python -m echopad` — first launch downloads the parakeet STT model (~0.6–1.2 GB), once.

Dictation runs fully locally (parakeet-mlx). Only speak-selection uses the network.

## Permissions (System Settings → Privacy & Security)
- Microphone: allow your terminal / the app.
- Accessibility: allow it (needed for global hotkeys + synthetic paste).

## Hotkeys (defaults, editable in config)
- Toggle dictation: ⌥⌘D
- Speak selection: ⌥⌘S
- Stop speaking: ⌥⌘.

## Manual verification

Requires a real `ELEVENLABS_API_KEY`, granted Microphone + Accessibility
permissions, and audio output. Run `python -m echopad` first (a 🎙️ icon appears
in the menubar).

**Dictation (local parakeet-mlx):**
1. Wait a few seconds after launch for the model to warm-load.
2. Click into a text field (e.g. TextEdit).
3. Press ⌥⌘D — the icon turns 🔴 (recording).
4. Speak a sentence, then press ⌥⌘D again — the icon shows ⏳ while transcribing,
   then the text is pasted and the icon returns to 🎙️.
5. Copy something beforehand and confirm it's still on your clipboard afterward.
6. Toggling on within a second of launch (model not loaded) shows a
   "still loading" notification instead of recording silently.

**Speak selection:**
1. Select a paragraph in any app.
2. Press ⌥⌘S — the icon shows 🔊 and a 2–3 sentence spoken summary plays.
3. Press ⌥⌘. mid-playback — audio stops.

**Error paths:**
- With nothing selected, press ⌥⌘S → a "Nothing selected" notification, no audio.
- Unset the key (`unset ELEVENLABS_API_KEY`) and run `python -m echopad` → it
  prints a clear configuration error and exits non-zero (no silent fallback).

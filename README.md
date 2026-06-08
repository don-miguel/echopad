# EchoPad

Local macOS menubar app: toggle dictation (ElevenLabs realtime STT → paste) and
speak-your-selection (MiniMax M3 summary → ElevenLabs TTS).

## Setup
1. `brew install portaudio`
2. `python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`
3. `export ELEVENLABS_API_KEY=...` (MINIMAX_API_KEY is expected to already be set)
4. `cp config.example.toml ~/.config/echopad/config.toml` and edit the voice id.
5. `python -m echopad`

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

**Dictation:**
1. Click into a text field (e.g. TextEdit).
2. Press ⌥⌘D — the menubar icon turns 🔴.
3. Speak a sentence; within ~1–2s it pastes into the field.
4. Press ⌥⌘D again — the icon returns to 🎙️.
5. Copy something beforehand and confirm it's still on your clipboard afterward
   (dictation saves and restores the clipboard).

**Speak selection:**
1. Select a paragraph in any app.
2. Press ⌥⌘S — the icon shows 🔊 and a 2–3 sentence spoken summary plays.
3. Press ⌥⌘. mid-playback — audio stops.

**Error paths:**
- With nothing selected, press ⌥⌘S → a "Nothing selected" notification, no audio.
- Unset the key (`unset ELEVENLABS_API_KEY`) and run `python -m echopad` → it
  prints a clear configuration error and exits non-zero (no silent fallback).

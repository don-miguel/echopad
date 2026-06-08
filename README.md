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

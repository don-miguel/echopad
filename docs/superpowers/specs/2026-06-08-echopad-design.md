# EchoPad — Design Spec

**Date:** 2026-06-08
**Status:** Approved (design phase)
**Platform:** macOS (Apple Silicon), Python + menubar

## Summary

EchoPad is a local macOS menubar app providing two voice features that talk
directly to ElevenLabs and MiniMax — no LiveKit, no server:

1. **Toggle dictation.** A hotkey turns dictation on. While on, the mic streams
   to ElevenLabs realtime STT (Scribe v2 Realtime) and each committed transcript
   segment is pasted into the currently focused app. The same hotkey turns it off.
2. **Speak selection.** A second hotkey captures the current text selection,
   summarizes it with MiniMax M3, and speaks the summary via ElevenLabs TTS.

LiveKit was considered and deliberately excluded: for a single-user local
dictation tool it adds a server/token dependency without earning its place. The
mic streams directly to ElevenLabs' realtime STT WebSocket.

## External services (verified 2026-06-08)

- **ElevenLabs Scribe v2 Realtime STT** — WebSocket API. Accepts PCM (8–48 kHz)
  audio, has built-in VAD, returns *partial* (live) and *committed* (finalized)
  transcripts. We act on committed segments.
  Docs: https://elevenlabs.io/docs/api-reference/speech-to-text/v-1-speech-to-text-realtime
- **ElevenLabs Streaming TTS** — text → streamed audio for low-latency playback.
- **MiniMax M3** — OpenAI-compatible Chat Completions.
  Base URL `https://api.minimax.io/v1`, model `MiniMax-M3`.
  Docs: https://platform.minimax.io/docs/api-reference/text-openai-api

## Configuration

- API keys come from the environment:
  - `ELEVENLABS_API_KEY` — **must be added by the user** (not yet present).
  - `MINIMAX_API_KEY` — already present in the user's environment.
- User config file (e.g. `~/.config/echopad/config.toml`) holds: hotkeys,
  ElevenLabs voice ID, STT language, model names, and summary style.
- **Fail fast on missing keys/config.** No fallback values, no silent defaults
  that mask a missing key — surface a clear, actionable error. (Per the user's
  global rule: never add fallback logic that covers up a missing dependency.)

### Defaults

- Hotkeys (configurable): Toggle dictation `⌥⌘D`, Speak selection `⌥⌘S`,
  Stop `⌥⌘.`.
- Summary style: concise 2–3 sentence gist (configurable to bullets / paragraph).
- STT language: auto (configurable).
- Audio capture: 16 kHz mono PCM.

## Components

Each module has one clear purpose and a small interface.

| Module | Responsibility | Depends on |
|--------|----------------|-----------|
| `config.py` | Load env keys + user config; fail fast if missing | env, config file |
| `mic.py` | Capture mic as 16 kHz mono PCM; yield frames | sounddevice |
| `stt.py` | ElevenLabs realtime STT WebSocket client; emit committed transcript segments | websockets, ElevenLabs |
| `tts.py` | ElevenLabs streaming TTS → audio playback; support interrupt/stop | sounddevice, ElevenLabs |
| `summarize.py` | MiniMax M3 (OpenAI-compatible) — selection text → summary | openai SDK |
| `clipboard.py` | macOS paste (Cmd+V) and selection-capture (Cmd+C), each saving & restoring prior clipboard | pbcopy/pbpaste, synthetic keys |
| `hotkeys.py` | Register global hotkeys → callbacks | pynput |
| `dictation.py` | Orchestrate dictation toggle: mic → STT → paste | mic, stt, clipboard |
| `speak_selection.py` | Orchestrate: capture selection → summarize → speak | clipboard, summarize, tts |
| `app.py` | rumps menubar; state machine (idle/listening/speaking); icon + menu; wires everything | rumps, all above |

## Data flow

**Dictation**

```
hotkey(toggle) → dictation.start()
    mic frames ──▶ stt WebSocket ──▶ committed text ──▶ clipboard.paste_text()
hotkey(toggle) → dictation.stop()  (close socket, stop mic)
```

**Speak selection**

```
hotkey(speak) → clipboard.capture_selection()   (synthetic Cmd+C + restore)
             → summarize(text)                  (MiniMax M3)
             → tts.speak(summary)               (streamed playback)
hotkey(stop)  → tts.stop()                       (interrupt playback)
```

## Key decisions & tradeoffs

- **Paste, not keystroke-typing.** Clipboard paste (Cmd+V) is fast and reliable
  across apps. We save the user's existing clipboard before pasting and restore
  it after, so dictation doesn't clobber it.
- **Selection capture via synthetic Cmd+C.** The only reliable cross-app way to
  read the current selection on macOS. Prior clipboard is saved and restored.
- **Committed (not partial) transcripts drive pasting.** Avoids pasting/retracting
  half-formed text. Partial transcripts may optionally update the menubar tooltip
  for feedback only.
- **macOS permissions required:** Microphone + Accessibility (global hotkeys and
  synthetic keystrokes). App detects missing grants and points the user to the
  right System Settings pane rather than failing opaquely.

## Error handling

- Missing API key or unreadable config → fail fast at startup with an actionable
  message naming the missing item.
- Missing Microphone / Accessibility permission → detect, notify, link to the
  System Settings pane; do not proceed silently.
- STT WebSocket drops mid-dictation → surface in the menubar + a notification,
  stop dictation cleanly. No silent auto-reconnect that hides the failure.
- Empty selection on Speak Selection → notify "nothing selected," no API calls.
- No silent fallbacks anywhere.

## Testing

- **Unit (with mocks):**
  - `config` — loads keys/config; fails fast and with a clear message when a key
    is missing.
  - `clipboard` — save/restore logic preserves prior clipboard contents.
  - `summarize` — given selection text, builds the right MiniMax request and
    returns the model's summary (mocked client).
  - `stt` — parses incoming WebSocket frames, distinguishes partial vs committed,
    emits only committed segments.
- **Manual checklist** (real hardware/permissions) for `hotkeys`, `mic`, paste
  into a live app, selection capture, TTS playback, and permission prompts.

## Out of scope (YAGNI)

- LiveKit / any server component.
- Wake-word or always-on continuous transcription (toggle mode only).
- Multi-provider summarizer abstraction (MiniMax M3 only for now).
- Cross-platform support (macOS only).

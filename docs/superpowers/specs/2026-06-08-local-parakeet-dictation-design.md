# EchoPad — Local parakeet-mlx Dictation (Design Spec)

**Date:** 2026-06-08
**Status:** Approved (design phase)
**Supersedes:** the dictation half of `2026-06-08-echopad-design.md` (speak-selection is unchanged)

## Summary

Replace EchoPad's dictation engine — currently ElevenLabs realtime WebSocket STT —
with a fully local **parakeet-mlx** model (`mlx-community/parakeet-tdt-0.6b-v2`)
running on Apple Silicon via MLX. Dictation becomes: toggle on → record locally,
toggle off → transcribe the recording and paste the full text at once. The
speak-selection feature (MiniMax M3 summarize + ElevenLabs TTS) is untouched.

This mirrors the user's proven `~/workspace/dictate/dictate.py` approach (local
MLX STT, high-pass + normalize preprocessing, clipboard-paste insertion), but
uses parakeet-mlx instead of mlx-whisper for faster, more accurate English STT.

## Decisions (confirmed)

- **Engine:** parakeet-mlx, model `mlx-community/parakeet-tdt-0.6b-v2`. English.
- **Paste timing:** once, on toggle-off (no incremental mid-utterance pasting —
  avoids chunk-boundary word splits).
- **Preprocessing:** keep the `~/dictate` pipeline — 80 Hz Butterworth high-pass +
  peak-normalize (scipy) — before transcription.
- **Backend stays swappable:** transcription sits behind a single
  `transcribe(audio, model, sample_rate) -> str` function so a different MLX model
  (e.g. whisper-turbo) is a config change, not a rewrite.

## What changes

- **Remove (dead after the switch):** `echopad/stt.py`, `tests/test_stt.py`.
- **`echopad/mic.py`:** replace the int16 `RawInputStream` block reader with a
  float32 16 kHz mono accumulating recorder (parakeet wants float32). New shape:
  an `AudioRecorder` context manager that starts an `InputStream` and collects
  frames; `get_audio()` returns the concatenated `np.float32` array.
- **`echopad/dictation.py`:** only `_default_runner` changes. It now records via
  `AudioRecorder` while `stop_event` is unset, then on stop runs
  `process_audio` → `transcribe` and calls `on_committed(text)` once. The
  `DictationController` (toggle / threading / `notify` / `on_state`) is unchanged,
  so the menubar wiring and existing tests keep working.
- **`echopad/config.py`:** the `[stt]` section swaps ElevenLabs fields
  (`audio_format`, the ws `model_id`, `language`) for parakeet settings:
  `model_repo` (default `mlx-community/parakeet-tdt-0.6b-v2`), `sample_rate`
  (default 16000), `highpass_cutoff` (default 80). `ELEVENLABS_API_KEY` remains
  **required** because TTS/speak-selection still uses it.
- **`echopad/app.py`:** warm-load the model at startup on a background thread;
  add a "transcribing" icon state shown between toggle-off and paste.

## New component: `echopad/transcriber.py`

One responsibility: audio array → text.

- `process_audio(audio: np.ndarray, sample_rate: int) -> np.ndarray` — 80 Hz
  high-pass (Butterworth, scipy `butter`/`sosfilt`) then peak-normalize to [-1, 1].
  Pure; unit-tested.
- `load_model(repo: str)` — `parakeet_mlx.from_pretrained(repo)`, module-level
  cached. Triggers the one-time model download. Called from a warm-load at startup.
- `transcribe(audio: np.ndarray, model, sample_rate: int) -> str` — runs the
  float32 array through parakeet and returns the stripped `.text`. Manual-tested
  (needs the model).

## Data flow (dictation)

```
⌥⌘D (on)  → DictationController.start → worker thread:
                AudioRecorder starts (float32, 16 kHz, mono), accumulating
⌥⌘D (off) → stop_event set → recorder stops → audio = recorder.get_audio()
                process_audio(audio) → transcribe(...) → on_committed(text)
                → paste_text(text + " ") with clipboard save/restore
```

Menubar icon states: idle 🎙️ → recording 🔴 → transcribing ⏳ → idle 🎙️. The
`on_state` callback (already thread-safe via the main-thread UI queue) drives these.

## Error handling

- Model not yet loaded when dictation toggled on → notify "model still loading,"
  do not start recording (or block briefly until loaded). No silent failure.
- Empty/near-silent recording → transcribe yields empty text → nothing pasted,
  brief "(nothing heard)" notification.
- parakeet import/load failure → fail fast with an actionable message naming the
  missing dependency. No fallback that hides a broken install (per project rule).

## Dependencies & risks

- **Add:** `parakeet-mlx` (pulls `mlx`), `scipy`. numpy already present.
- **Risk 1 — Python 3.14 support (spike first):** the echopad venv is Python
  3.14; parakeet-mlx/mlx wheels may not support it. Implementation Task 1 is a
  spike: install + load + transcribe a clip. If it fails, rebuild the venv on
  Python 3.12 (the version `~/workspace/dictate/.venv` uses, which already runs
  MLX). This risk is resolved before any feature code is written.
- **Risk 2 — first-run download:** `parakeet-tdt-0.6b-v2` (~0.6–1.2 GB) downloads
  on first model load (network once, then fully offline). Only whisper-turbo is
  currently cached.

## Testing

- **Unit:** `process_audio` (returns float32, same length, peak ≤ 1.0, attenuates
  a low-frequency/DC component); `config` (new `[stt]` parakeet fields + defaults).
- **Unchanged & still green:** dictation controller tests (runner is injected),
  speak-selection, clipboard, summarize, tts, mic-timeout-None.
- **Manual:** record speech → correct transcription pasted into a focused app;
  clipboard preserved; "transcribing" state shows; empty recording handled.

## Out of scope (YAGNI)

- Incremental/streaming paste (parakeet supports streaming; not in v1).
- Context-aware dictation / keyterm biasing (shelved earlier this session).
- Multiple selectable STT engines at runtime (kept swappable via config only).
- Always-on mic / pre-roll ring buffer (recording starts on toggle, per the
  user's toggle-not-always-listening preference).

# EchoPad — Live (Continuous) Dictation with Pause-Based Pasting

**Date:** 2026-06-08
**Status:** Approved (design phase)
**Changes:** the dictation runner only. Speak-selection and the local parakeet
transcription path are unchanged.

## Summary

Change dictation from "record the whole session, transcribe once at toggle-off,
paste once" to **continuous live listening**: while dictation is on, EchoPad
keeps capturing audio and, each time the speaker pauses, transcribes that
utterance and pastes it — then keeps listening until toggled off. Pauses are
detected with WebRTC voice-activity detection (`webrtcvad`). Because segments are
cut at pauses (not arbitrary time boundaries), no words are split.

## Decisions (confirmed)

- **Pause detection:** `webrtcvad` (Google WebRTC VAD) — tiny C library, no model.
- **Toggle hotkey:** **Opt+Delete** (`<alt>+<delete>`), replacing the previous
  `<cmd>+<alt>+d`. (Mirrors the user's `~/dictate`. Note: Opt+Delete also deletes
  a word in a focused field, and pynput global hotkeys don't suppress the
  keystroke — accepted; configurable.)
- **Default pause length:** 0.7 s of silence closes an utterance.
- **Speak-selection (⌥⌘S) and stop (⌥⌘.) hotkeys:** unchanged.

## Flow

```
Opt+Delete (on) → continuous 16 kHz mono capture, sliced into 30 ms frames
  each frame → webrtcvad.is_speech?
  speech…speech…[silence ≥ pause_seconds] → close segment
        → transcribe segment (dedicated MLX thread) → paste + " " → keep listening
Opt+Delete (off) → flush any in-progress speech → transcribe → paste → stop
```

Capture continues during transcription (transcription runs on the MLX thread, the
audio callback keeps filling frames), so speech is never dropped between utterances.

## Components

- **New `echopad/vad.py`**
  - `frame_to_pcm16_bytes(frame: np.ndarray) -> bytes` — float32 [-1,1] → 16-bit
    little-endian PCM bytes (what webrtcvad consumes). Pure; unit-tested.
  - `Segmenter(pause_frames: int, frame_ms: int = 30)` — a pure state machine.
    `push(is_speech: bool, frame: np.ndarray) -> np.ndarray | None` returns a
    completed audio segment (concatenated frames) when a speech run is followed by
    `pause_frames` consecutive silent frames; otherwise `None`. Brief silences
    shorter than the threshold do not split an utterance. `flush() -> np.ndarray |
    None` returns any trailing speech when dictation stops. Pure; unit-tested with
    boolean sequences (no audio or webrtcvad needed).
  - The webrtcvad instance (`webrtcvad.Vad(aggressiveness)`) lives in the runner;
    it maps each frame's PCM bytes → bool and feeds the `Segmenter`.

- **`echopad/dictation.py` `_default_runner`** — rewritten as the continuous loop:
  open an `InputStream` (float32, 16 kHz) whose callback enqueues fixed 30 ms
  frames; pull frames until `stop_event`, run webrtcvad → `Segmenter`; for each
  returned segment, `process_audio` → `transcribe` → `on_committed`. On stop,
  `flush()` and transcribe the remainder. The `DictationController` is unchanged —
  `on_committed` now fires once per utterance instead of once per session.

- **`echopad/config.py`** — add to `[stt]`/config: `vad_aggressiveness` (0–3,
  default 2), `pause_seconds` (default 0.7), `vad_frame_ms` (default 30). Change
  the `toggle_dictation` hotkey default to `<alt>+<delete>`.

- **`echopad/mic.py`** — provide a frame-oriented capture suitable for VAD
  (fixed-size 30 ms frames via the stream callback into a queue). The existing
  `AudioRecorder` (whole-buffer) is replaced or supplemented by a
  `FrameStream`-style capture that yields 30 ms frames.

- **Menubar** — stays 🔴 while listening; ⏳ may flash during a segment's
  transcription. No new states required.

## Error handling

- `webrtcvad` import/instantiation failure → fail fast with an actionable message
  naming the dependency (no silent fallback).
- No audio captured (mic permission) → the existing "check Microphone permission"
  log path still applies (no frames arrive → no segments → a logged warning on stop).
- An empty/garbage segment transcribing to empty text → nothing pasted (logged).

## Testing

- **Unit:** `Segmenter` — (a) speech then ≥ threshold silence emits one segment;
  (b) a short silence inside speech does not split; (c) two utterances emit two
  segments; (d) `flush` emits trailing speech, returns `None` when idle.
  `frame_to_pcm16_bytes` — correct length (samples×2) and int16 encoding.
- **Unchanged & green:** transcriber (incl. thread-affinity), speak-selection,
  clipboard, summarize, tts, config.
- **Manual:** toggle on, speak several sentences with pauses; confirm each pastes
  shortly after each pause and listening continues; toggle off flushes the last
  utterance.

## Risks

- **`webrtcvad` on Python 3.14:** the original package is a C extension that may
  not build on 3.14. Implementation Task 1 is a spike: install + instantiate +
  classify a frame. Fall back to the prebuilt `webrtcvad-wheels` if the build fails.

## Out of scope (YAGNI)

- Streaming/partial transcripts within an utterance (we transcribe whole utterances
  at pauses).
- Adaptive/auto-calibrated VAD thresholds (fixed aggressiveness + pause length,
  configurable).
- Context-aware dictation / keyterm biasing (still shelved).

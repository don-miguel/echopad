# Live Dictation (VAD Pause-Based) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Change dictation from record-then-transcribe-once into continuous live listening that transcribes and pastes each utterance when the speaker pauses, using webrtcvad for pause detection.

**Architecture:** A new pure `Segmenter` state machine (in `vad.py`) turns a stream of per-frame speech/silence booleans into utterance segments. A frame-oriented `FrameStream` (in `mic.py`) yields exact 30 ms frames. The dictation runner loops: frame → webrtcvad → Segmenter → on each segment, transcribe (on the dedicated MLX thread) and paste. The `DictationController` is unchanged — `on_committed` now fires once per utterance.

**Tech Stack:** webrtcvad (or webrtcvad-wheels), parakeet-mlx, sounddevice, numpy, scipy. Python 3.14.

---

## File Structure

```
echopad/
  vad.py        # NEW: frame_to_pcm16_bytes + Segmenter state machine
  mic.py        # add FrameStream (exact 30ms frames); remove AudioRecorder (Task 5)
  dictation.py  # _default_runner → continuous webrtcvad loop
  config.py     # vad_aggressiveness, pause_seconds, vad_frame_ms; toggle default → opt+delete
tests/
  test_vad.py   # NEW
  test_mic.py   # rewritten for FrameStream
  test_config.py# new VAD fields + new hotkey default
```

**Naming contract:**
- `vad.frame_to_pcm16_bytes(frame: np.ndarray) -> bytes`
- `vad.Segmenter(pause_frames: int, frame_ms: int = 30)` with `push(is_speech: bool, frame: np.ndarray) -> np.ndarray | None` and `flush() -> np.ndarray | None`
- `mic.FrameStream(sample_rate=16000, frame_ms=30)` context manager; `.frame_samples: int`; `.read_frame(timeout=None) -> np.ndarray | None`
- Config gains `vad_aggressiveness: int`, `pause_seconds: float`, `vad_frame_ms: int`; `hotkeys.toggle_dictation` default becomes `<alt>+<delete>`.

---

## Task 1: Spike — webrtcvad on Python 3.14

**Files:** Modify `requirements.txt`

- [ ] **Step 1: Try installing webrtcvad**

Run:
```bash
cd ~/echopad && source .venv/bin/activate
pip install webrtcvad
```
If the build fails (no 3.14 wheel / compiler error), instead run `pip install webrtcvad-wheels` (a prebuilt-wheel drop-in that also imports as `webrtcvad`). Note which one worked.

- [ ] **Step 2: Verify it classifies a frame**

Run:
```bash
python -c "
import webrtcvad
v = webrtcvad.Vad(2)
silence = b'\x00\x00' * 480           # 30ms of 16kHz 16-bit silence = 480 samples
print('is_speech(silence) =', v.is_speech(silence, 16000))
"
```
Expected: prints `is_speech(silence) = False` with no error. If it errors, report BLOCKED.

- [ ] **Step 3: Pin in `requirements.txt`** — append the line that worked (one of):
```
webrtcvad
```
(or `webrtcvad-wheels` if that's what installed). Place it after the `parakeet-mlx` line.

- [ ] **Step 4: Suite still green**

Run: `pytest -q`
Expected: all current tests pass (31).

- [ ] **Step 5: Commit**

```bash
git add requirements.txt
git commit -m "chore: add webrtcvad; verify it loads"
```

---

## Task 2: vad.py — frame encoding + Segmenter

**Files:** Create `echopad/vad.py`; Test `tests/test_vad.py`

- [ ] **Step 1: Write failing tests `tests/test_vad.py`**

```python
import numpy as np
from echopad.vad import frame_to_pcm16_bytes, Segmenter


def _f(value, n=4):
    return np.full(n, value, dtype=np.float32)


def test_frame_to_pcm16_bytes_length_and_encoding():
    frame = np.array([0.0, 1.0, -1.0], dtype=np.float32)
    data = frame_to_pcm16_bytes(frame)
    assert len(data) == 3 * 2  # int16 = 2 bytes/sample
    decoded = np.frombuffer(data, dtype="<i2")
    assert decoded[0] == 0
    assert decoded[1] == 32767
    assert decoded[2] == -32767


def test_emits_segment_after_pause():
    seg = Segmenter(pause_frames=3)
    assert seg.push(True, _f(1.0)) is None   # speech
    assert seg.push(True, _f(1.0)) is None   # speech
    assert seg.push(False, _f(0.0)) is None  # silence 1
    assert seg.push(False, _f(0.0)) is None  # silence 2
    out = seg.push(False, _f(0.0))           # silence 3 -> pause reached
    assert out is not None
    assert 1.0 in out                        # contains the speech


def test_brief_silence_does_not_split():
    seg = Segmenter(pause_frames=3)
    seg.push(True, _f(1.0))
    assert seg.push(False, _f(0.0)) is None   # silence 1 (< pause)
    assert seg.push(False, _f(0.0)) is None   # silence 2 (< pause)
    assert seg.push(True, _f(2.0)) is None    # speech resumes -> no split
    seg.push(False, _f(0.0))
    seg.push(False, _f(0.0))
    out = seg.push(False, _f(0.0))            # now 3 in a row
    assert out is not None
    assert 1.0 in out and 2.0 in out          # single segment spans both


def test_two_utterances_emit_two_segments():
    seg = Segmenter(pause_frames=2)
    seg.push(True, _f(1.0))
    seg.push(False, _f(0.0))
    a = seg.push(False, _f(0.0))
    seg.push(True, _f(2.0))
    seg.push(False, _f(0.0))
    b = seg.push(False, _f(0.0))
    assert a is not None and 1.0 in a
    assert b is not None and 2.0 in b


def test_flush_returns_trailing_speech_then_none():
    seg = Segmenter(pause_frames=3)
    seg.push(True, _f(5.0))
    seg.push(True, _f(5.0))
    out = seg.flush()
    assert out is not None and 5.0 in out
    assert seg.flush() is None                # nothing left


def test_silence_before_speech_ignored():
    seg = Segmenter(pause_frames=2)
    assert seg.push(False, _f(0.0)) is None
    assert seg.push(False, _f(0.0)) is None
    assert seg.flush() is None
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_vad.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'echopad.vad'`.

- [ ] **Step 3: Write `echopad/vad.py`**

```python
import numpy as np


def frame_to_pcm16_bytes(frame: np.ndarray) -> bytes:
    """Convert a float32 [-1, 1] frame to little-endian 16-bit PCM bytes."""
    pcm = (np.clip(frame, -1.0, 1.0) * 32767).astype("<i2")
    return pcm.tobytes()


class Segmenter:
    """Turn per-frame speech/silence decisions into utterance segments.

    Push one frame at a time. While speech is active, frames (including brief
    internal silences) are collected. When `pause_frames` consecutive silent
    frames follow speech, the collected audio is returned as one segment.
    """

    def __init__(self, pause_frames: int, frame_ms: int = 30):
        self.pause_frames = pause_frames
        self.frame_ms = frame_ms
        self._frames: list[np.ndarray] = []
        self._in_speech = False
        self._silence_run = 0

    def push(self, is_speech: bool, frame: np.ndarray) -> np.ndarray | None:
        if is_speech:
            self._frames.append(frame)
            self._in_speech = True
            self._silence_run = 0
            return None
        if not self._in_speech:
            return None  # silence before any speech — ignore
        self._frames.append(frame)
        self._silence_run += 1
        if self._silence_run >= self.pause_frames:
            return self._emit()
        return None

    def flush(self) -> np.ndarray | None:
        if not self._in_speech:
            self._reset()
            return None
        return self._emit()

    def _emit(self) -> np.ndarray:
        segment = np.concatenate(self._frames)
        self._reset()
        return segment

    def _reset(self) -> None:
        self._frames = []
        self._in_speech = False
        self._silence_run = 0
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_vad.py -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add echopad/vad.py tests/test_vad.py
git commit -m "feat: VAD segmenter and PCM16 frame encoding"
```

---

## Task 3: mic.py — FrameStream

**Files:** Modify `echopad/mic.py` (add `FrameStream`); rewrite `tests/test_mic.py`

`AudioRecorder` stays for now (still imported by `dictation.py`); it is removed in Task 5.

- [ ] **Step 1: Rewrite `tests/test_mic.py`**

```python
import numpy as np
from echopad.mic import FrameStream


def test_frame_samples_computed():
    fs = FrameStream(sample_rate=16000, frame_ms=30)
    assert fs.frame_samples == 480


def test_read_frame_returns_exact_frame_size():
    fs = FrameStream(sample_rate=16000, frame_ms=30)
    # Feed odd-sized blocks; read_frame must re-chunk to exactly frame_samples.
    fs._queue.put(np.ones(200, dtype=np.float32))
    fs._queue.put(np.ones(400, dtype=np.float32))
    frame = fs.read_frame(timeout=0.1)
    assert frame is not None
    assert frame.shape[0] == 480
    assert frame.dtype == np.float32


def test_read_frame_timeout_returns_none():
    fs = FrameStream()
    assert fs.read_frame(timeout=0.01) is None
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_mic.py -v`
Expected: FAIL — `ImportError: cannot import name 'FrameStream'`.

- [ ] **Step 3: Add `FrameStream` to `echopad/mic.py`** (append below the existing `AudioRecorder` class; add `import queue` at the top if not present)

```python
import queue


class FrameStream:
    """Capture mono float32 audio and yield exact `frame_ms` frames.

    Used for VAD, which requires precise 10/20/30 ms frames. read_frame()
    re-chunks the callback blocks so each returned frame is exactly
    frame_samples long.
    """

    def __init__(self, sample_rate: int = 16000, frame_ms: int = 30):
        self.sample_rate = sample_rate
        self.frame_ms = frame_ms
        self.frame_samples = int(sample_rate * frame_ms / 1000)
        self._queue: "queue.Queue[np.ndarray]" = queue.Queue()
        self._buf = np.zeros(0, dtype=np.float32)
        self._stream: sd.InputStream | None = None

    def _callback(self, indata, frames, time_info, status):
        self._queue.put(indata[:, 0].copy())

    def __enter__(self) -> "FrameStream":
        self._buf = np.zeros(0, dtype=np.float32)
        self._stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype="float32",
            blocksize=self.frame_samples,
            callback=self._callback,
        )
        self._stream.start()
        return self

    def read_frame(self, timeout: float | None = None) -> np.ndarray | None:
        while self._buf.size < self.frame_samples:
            try:
                block = self._queue.get(timeout=timeout)
            except queue.Empty:
                return None
            self._buf = np.concatenate([self._buf, block])
        frame = self._buf[: self.frame_samples]
        self._buf = self._buf[self.frame_samples :]
        return frame

    def __exit__(self, *exc) -> None:
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
```

(Note: `mic.py` already imports `numpy as np` and `sounddevice as sd`. Ensure `import queue` is present.)

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_mic.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add echopad/mic.py tests/test_mic.py
git commit -m "feat: FrameStream for exact-size VAD frames"
```

---

## Task 4: config.py — VAD settings + opt+delete default

**Files:** Modify `echopad/config.py`; Test `tests/test_config.py`

- [ ] **Step 1: Update `tests/test_config.py`** — change the toggle-default assertion and add VAD assertions. In `test_defaults_when_no_toml`, change:
```python
    assert cfg.hotkeys.toggle_dictation == "<cmd>+<alt>+d"
```
to:
```python
    assert cfg.hotkeys.toggle_dictation == "<alt>+<delete>"
```
Then add this new test after `test_parakeet_defaults`:
```python
def test_vad_defaults():
    cfg = load_config(config_path=None, env=_env())
    assert cfg.vad_aggressiveness == 2
    assert cfg.pause_seconds == 0.7
    assert cfg.vad_frame_ms == 30


def test_vad_toml_overrides(tmp_path):
    p = tmp_path / "config.toml"
    p.write_text("[stt]\nvad_aggressiveness = 3\npause_seconds = 1.0\nvad_frame_ms = 20\n")
    cfg = load_config(config_path=p, env=_env())
    assert cfg.vad_aggressiveness == 3
    assert cfg.pause_seconds == 1.0
    assert cfg.vad_frame_ms == 20
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_config.py::test_vad_defaults -v`
Expected: FAIL — `AttributeError: 'Config' object has no attribute 'vad_aggressiveness'`.

- [ ] **Step 3: Edit `echopad/config.py`**

In the `Config` dataclass, add after `stt_highpass_cutoff: int`:
```python
    vad_aggressiveness: int
    pause_seconds: float
    vad_frame_ms: int
```

In `load_config`, in the `Config(...)` call, add after the `stt_highpass_cutoff=...` line:
```python
        vad_aggressiveness=int(stt.get("vad_aggressiveness", 2)),
        pause_seconds=float(stt.get("pause_seconds", 0.7)),
        vad_frame_ms=int(stt.get("vad_frame_ms", 30)),
```

In `load_config`, change the `Hotkeys(...)` toggle default:
```python
            toggle_dictation=hk.get("toggle_dictation", "<alt>+<delete>"),
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_config.py -v`
Expected: PASS (existing + 2 new VAD tests).

- [ ] **Step 5: Commit**

```bash
git add echopad/config.py tests/test_config.py
git commit -m "feat: VAD config (aggressiveness/pause/frame); opt+delete toggle default"
```

---

## Task 5: dictation.py — continuous webrtcvad runner

**Files:** Modify `echopad/dictation.py`; Modify `echopad/mic.py` (remove `AudioRecorder`)

The `DictationController` class is unchanged. Only `_default_runner` and the imports change.

- [ ] **Step 1: Replace the imports and `_default_runner` in `echopad/dictation.py`.**

Change the import block at the top from:
```python
from echopad.mic import AudioRecorder
from echopad.transcriber import is_model_loaded, load_model, process_audio, transcribe
```
to:
```python
from echopad.mic import FrameStream
from echopad.transcriber import is_model_loaded, load_model, process_audio, transcribe
from echopad.vad import Segmenter, frame_to_pcm16_bytes
```

Replace the entire `_default_runner` function with:
```python
def _default_runner(config, stop_event, on_committed, set_state) -> None:
    """Continuously listen; transcribe & emit each utterance at a pause."""
    import webrtcvad

    if not is_model_loaded(config.stt_model_repo):
        raise RuntimeError("Speech model is still loading; try again in a moment.")
    model = load_model(config.stt_model_repo)

    vad = webrtcvad.Vad(config.vad_aggressiveness)
    pause_frames = max(1, round(config.pause_seconds * 1000 / config.vad_frame_ms))
    segmenter = Segmenter(pause_frames, config.vad_frame_ms)

    def handle(segment) -> None:
        if segment is None or segment.size == 0:
            return
        set_state("transcribing")
        processed = process_audio(segment, config.sample_rate, config.stt_highpass_cutoff)
        text = transcribe(processed, model, config.sample_rate)
        if text:
            log.info("Transcribed: %r — pasting.", text)
            on_committed(text)
        else:
            log.info("Utterance produced no text.")
        set_state("listening")

    log.info("Listening… (toggle the hotkey again to stop)")
    with FrameStream(sample_rate=config.sample_rate, frame_ms=config.vad_frame_ms) as frames:
        while not stop_event.is_set():
            frame = frames.read_frame(timeout=0.2)
            if frame is None:
                continue
            is_speech = vad.is_speech(frame_to_pcm16_bytes(frame), config.sample_rate)
            handle(segmenter.push(is_speech, frame))
        handle(segmenter.flush())
```

- [ ] **Step 2: Remove `AudioRecorder` from `echopad/mic.py`.** Delete the entire `AudioRecorder` class (keep `FrameStream` and the imports). Confirm nothing else imports it:

Run: `grep -rn "AudioRecorder" echopad tests`
Expected: no matches.

- [ ] **Step 3: Run the full suite**

Run: `pytest -q`
Expected: all pass (controller tests use an injected runner, so they're unaffected; the new runner glue is verified manually).

- [ ] **Step 4: Smoke-test imports**

Run: `python -c "import echopad.dictation, echopad.app; print('ok')"`
Expected: prints `ok`.

- [ ] **Step 5: Commit**

```bash
git add echopad/dictation.py echopad/mic.py
git commit -m "feat: continuous live dictation with webrtcvad pause segmentation"
```

---

## Task 6: config.example.toml + README + manual verification

**Files:** Modify `config.example.toml`, `README.md`

- [ ] **Step 1: Update `config.example.toml`** — replace the `[stt]` block with:

```toml
[stt]
model_repo = "mlx-community/parakeet-tdt-0.6b-v2"  # local MLX STT model
sample_rate = 16000
highpass_cutoff = 80      # Hz; high-pass to cut low-frequency noise before STT
vad_aggressiveness = 2    # 0-3; higher = more aggressively treats audio as non-speech
pause_seconds = 0.7       # silence this long ends an utterance and pastes it
vad_frame_ms = 30         # VAD frame size (10, 20, or 30)
```

And change the `[hotkeys]` toggle line to:
```toml
toggle_dictation = "<alt>+<delete>"   # Opt+Delete
```

- [ ] **Step 2: Update `README.md`** — change the dictation feature bullet and hotkey line. Replace the Dictation feature bullet under "## Features" with:

```markdown
- **Dictation (⌥Delete)** — toggle on and just talk; EchoPad listens continuously
  and, **each time you pause**, transcribes that utterance **on-device** with
  [parakeet-mlx](https://github.com/senstella/parakeet-mlx) and pastes it. Toggle
  off to stop. The clipboard is saved and restored.
```

And under "## Hotkeys (defaults, editable in config)" change the dictation line to:
```markdown
- Toggle dictation: ⌥Delete (Opt+Delete)
```

And replace the **Dictation (local parakeet-mlx):** block under "## Manual verification" with:
```markdown
**Dictation (live, local parakeet-mlx):**
1. Wait a few seconds after launch for `Speech model ready` in the terminal.
2. Click into a text field (e.g. TextEdit).
3. Press ⌥Delete — the icon turns 🔴 (listening).
4. Speak a sentence and pause — within ~1s the text pastes; keep talking and each
   pause pastes the next utterance.
5. Press ⌥Delete again to stop (the final utterance flushes and pastes).
6. The terminal logs `Transcribed: '...'` for each utterance.
```

- [ ] **Step 3: Manual verification**

```bash
cd ~/echopad && source .venv/bin/activate && python -m echopad
```
Confirm: ⌥Delete toggles listening; speaking with pauses pastes each utterance and listening continues; toggle-off flushes the last utterance; clipboard preserved; terminal logs each `Transcribed:`.

- [ ] **Step 4: Commit**

```bash
git add config.example.toml README.md
git commit -m "docs: live dictation + opt+delete hotkey in config and README"
```

---

## Self-Review Notes (addressed)

- **Spec coverage:** webrtcvad pause detection (Tasks 1,5); `Segmenter` + frame encoding (Task 2); FrameStream exact frames (Task 3); VAD config + opt+delete default (Task 4); continuous runner with per-utterance paste + flush-on-stop (Task 5); docs/manual (Task 6); Python-3.14 webrtcvad risk spike (Task 1). All covered.
- **Green at every commit:** `AudioRecorder` kept until Task 5 switches the runner to `FrameStream`; new config fields added before the runner consumes them.
- **No placeholders:** every code/test step is complete.
- **Type consistency:** `Segmenter(pause_frames, frame_ms)` / `push` / `flush`, `frame_to_pcm16_bytes`, `FrameStream.read_frame`/`frame_samples`, and Config `vad_aggressiveness`/`pause_seconds`/`vad_frame_ms` are used consistently across Tasks 2–6.
```

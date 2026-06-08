# Local parakeet-mlx Dictation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace EchoPad's dictation engine (ElevenLabs realtime WebSocket STT) with a fully local parakeet-mlx model — record on toggle-on, transcribe and paste on toggle-off. Speak-selection (MiniMax + ElevenLabs TTS) is untouched.

**Architecture:** A new `transcriber.py` (audio→text via parakeet-mlx + scipy preprocessing) and a float32 `AudioRecorder` in `mic.py` replace the WebSocket pipeline. `dictation.py`'s injected `runner` is rewritten to record-then-transcribe; the `DictationController` interface stays so the menubar and tests survive. The dead `stt.py` is removed and `config.py`'s `[stt]` section swaps to parakeet settings. The model is warm-loaded at app startup.

**Tech Stack:** parakeet-mlx (`mlx-community/parakeet-tdt-0.6b-v2`), MLX, scipy (high-pass + wav write), numpy, sounddevice, rumps, pynput. Python 3.14 if it supports MLX, else 3.12 (resolved in Task 1).

---

## File Structure

```
echopad/
  config.py          # [stt] section: parakeet model_repo + highpass_cutoff (Tasks 2, 6)
  transcriber.py     # NEW: highpass/normalize/process_audio + load_model/is_model_loaded/transcribe (Task 3)
  mic.py             # AudioRecorder (float32 accumulating recorder) — replaces MicStream (Task 4)
  dictation.py       # _default_runner rewritten to record→transcribe; runner gains set_state (Task 4)
  app.py             # warm-load model at startup, "transcribing" icon, no manual state in _on_toggle (Task 7)
  stt.py             # DELETED (Task 5)
tests/
  test_transcriber.py  # NEW (Task 3)
  test_mic.py          # rewritten for AudioRecorder (Task 4)
  test_dictation.py    # runner signature updated (Task 4)
  test_config.py       # parakeet fields (Tasks 2, 6)
  test_stt.py          # DELETED (Task 5)
```

**Naming contract (used across tasks):**
- Config gains `stt_model_repo: str` and `stt_highpass_cutoff: int`; keeps `sample_rate: int`. Tasks 2/6 add these and remove the old `stt_model_id`, `stt_language`, `stt_audio_format`.
- `transcriber.highpass(audio, sample_rate, cutoff=80) -> np.ndarray`
- `transcriber.normalize(audio) -> np.ndarray`
- `transcriber.process_audio(audio, sample_rate, highpass_cutoff=80) -> np.ndarray`
- `transcriber.load_model(repo) -> model` (module-cached); `transcriber.is_model_loaded(repo) -> bool`
- `transcriber.transcribe(audio, model, sample_rate) -> str`
- `mic.AudioRecorder(sample_rate=16000)` context manager; `.get_audio() -> np.ndarray` (float32, empty array if nothing recorded)
- `dictation` Runner signature: `(config, stop_event, on_committed, set_state)` where `set_state(str)`.

---

## Task 1: Feasibility spike — parakeet-mlx in the venv (or rebuild on 3.12)

**Files:**
- Modify: `requirements.txt`

This is an exploratory gate, not TDD. It must end with a venv where parakeet-mlx loads and transcribes, and `requirements.txt` updated.

- [ ] **Step 1: Add deps to `requirements.txt`** (append these two lines)

```
scipy>=1.13
parakeet-mlx
```

- [ ] **Step 2: Try installing in the current (Python 3.14) venv**

Run:
```bash
cd ~/echopad && source .venv/bin/activate
python -V
pip install scipy parakeet-mlx
```
If install fails (no MLX/parakeet wheels for 3.14), go to Step 3. If it succeeds, skip Step 3.

- [ ] **Step 3 (only if Step 2 failed): rebuild the venv on Python 3.12 in place**

```bash
cd ~/echopad
deactivate 2>/dev/null || true
# find a 3.12 interpreter; install one if absent
command -v python3.12 || brew install python@3.12
rm -rf .venv
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```
`requirements.txt` already lists every prior dep plus scipy + parakeet-mlx, so this reinstalls everything. If `pyobjc-framework-ApplicationServices==11.1` has no 3.12 wheel, change it to the nearest version that does and note the change.

- [ ] **Step 4: End-to-end verify (install + model download + transcription)**

Run:
```bash
say "the quick brown fox" -o /tmp/say.aiff
ffmpeg -y -loglevel error -i /tmp/say.aiff -ar 16000 -ac 1 /tmp/say.wav
python -c "from parakeet_mlx import from_pretrained; m=from_pretrained('mlx-community/parakeet-tdt-0.6b-v2'); print('TRANSCRIPT:', m.transcribe('/tmp/say.wav').text)"
```
Expected: downloads the model (~0.6–1.2 GB, first time only), then prints `TRANSCRIPT:` containing "quick brown fox" (case/punctuation may vary). If the transcript is empty or errors, report BLOCKED with the full error — do not proceed.

- [ ] **Step 5: Verify the existing suite still passes in this venv**

Run: `pytest -q`
Expected: all current tests pass (the dictation suite from before — should be 26).

- [ ] **Step 6: Commit**

```bash
git add requirements.txt
git commit -m "chore: add parakeet-mlx + scipy; verify local STT works"
```

- [ ] **Step 7: Report** the Python version used and whether a 3.12 rebuild was needed, so later tasks use the right interpreter.

---

## Task 2: config.py — add parakeet `[stt]` fields (keep old ones for now)

**Files:**
- Modify: `echopad/config.py`, `config.example.toml`
- Test: `tests/test_config.py`

Adding (not yet removing) keeps `stt.py`/`test_stt.py` green until they're deleted in Task 5.

- [ ] **Step 1: Add failing assertions to `tests/test_config.py`**

Add these two tests after `test_defaults_when_no_toml`:
```python
def test_parakeet_defaults():
    cfg = load_config(config_path=None, env=_env())
    assert cfg.stt_model_repo == "mlx-community/parakeet-tdt-0.6b-v2"
    assert cfg.stt_highpass_cutoff == 80
    assert cfg.sample_rate == 16000


def test_parakeet_toml_overrides(tmp_path):
    p = tmp_path / "config.toml"
    p.write_text('[stt]\nmodel_repo = "mlx-community/other"\nhighpass_cutoff = 120\n')
    cfg = load_config(config_path=p, env=_env())
    assert cfg.stt_model_repo == "mlx-community/other"
    assert cfg.stt_highpass_cutoff == 120
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_config.py::test_parakeet_defaults -v`
Expected: FAIL with `AttributeError: 'Config' object has no attribute 'stt_model_repo'`.

- [ ] **Step 3: Add the fields to `echopad/config.py`**

In the `Config` dataclass, add these two fields (place them right after `sample_rate: int`):
```python
    stt_model_repo: str
    stt_highpass_cutoff: int
```

In `load_config`, in the `Config(...)` constructor call, add these two keyword arguments (place them right after `sample_rate=int(stt.get("sample_rate", 16000)),`):
```python
        stt_model_repo=stt.get("model_repo", "mlx-community/parakeet-tdt-0.6b-v2"),
        stt_highpass_cutoff=int(stt.get("highpass_cutoff", 80)),
```

- [ ] **Step 4: Update `config.example.toml`** — replace the `[stt]` block with:

```toml
[stt]
model_repo = "mlx-community/parakeet-tdt-0.6b-v2"  # local MLX STT model
sample_rate = 16000
highpass_cutoff = 80   # Hz; high-pass to cut low-frequency noise before STT
```

- [ ] **Step 5: Run config tests**

Run: `pytest tests/test_config.py -v`
Expected: PASS (existing tests + the 2 new ones).

- [ ] **Step 6: Commit**

```bash
git add echopad/config.py config.example.toml tests/test_config.py
git commit -m "feat: add parakeet model_repo + highpass_cutoff config"
```

---

## Task 3: transcriber.py — audio preprocessing + parakeet transcription

**Files:**
- Create: `echopad/transcriber.py`
- Test: `tests/test_transcriber.py`

- [ ] **Step 1: Write failing tests `tests/test_transcriber.py`**

```python
import numpy as np
from echopad.transcriber import highpass, normalize, process_audio


def _tone(freq, sr=16000, seconds=1.0, amp=1.0):
    t = np.linspace(0, seconds, int(sr * seconds), endpoint=False)
    return (amp * np.sin(2 * np.pi * freq * t)).astype(np.float32)


def test_highpass_attenuates_low_frequency():
    sr = 16000
    low = _tone(10, sr=sr, amp=1.0)  # 10 Hz, well below the 80 Hz cutoff
    out = highpass(low, sr, cutoff=80)
    assert out.dtype == np.float32
    assert np.max(np.abs(out)) < 0.2  # strongly attenuated


def test_highpass_passes_high_frequency():
    sr = 16000
    high = _tone(1000, sr=sr, amp=0.5)  # well above cutoff
    out = highpass(high, sr, cutoff=80)
    assert np.max(np.abs(out)) > 0.4  # roughly preserved


def test_normalize_scales_peak_to_one():
    out = normalize(np.array([0.0, 0.1, -0.2], dtype=np.float32))
    assert np.isclose(np.max(np.abs(out)), 1.0, atol=1e-6)


def test_normalize_silence_is_unchanged():
    out = normalize(np.zeros(8, dtype=np.float32))
    assert np.max(np.abs(out)) == 0.0  # no divide-by-zero


def test_process_audio_float32_same_length():
    sr = 16000
    audio = _tone(1000, sr=sr, amp=0.3)
    out = process_audio(audio, sr)
    assert out.dtype == np.float32
    assert out.shape == audio.shape
    assert np.max(np.abs(out)) <= 1.0 + 1e-6
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_transcriber.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'echopad.transcriber'`.

- [ ] **Step 3: Write `echopad/transcriber.py`**

```python
import numpy as np
from scipy.signal import butter, sosfilt

_MODEL_CACHE: dict = {}


def highpass(audio: np.ndarray, sample_rate: int, cutoff: int = 80) -> np.ndarray:
    """Butterworth high-pass to remove low-frequency rumble (HVAC, handling)."""
    sos = butter(5, cutoff, btype="high", fs=sample_rate, output="sos")
    return sosfilt(sos, audio).astype(np.float32)


def normalize(audio: np.ndarray) -> np.ndarray:
    """Peak-normalize to [-1, 1]; silence passes through unchanged."""
    peak = float(np.max(np.abs(audio))) if audio.size else 0.0
    if peak > 0:
        return (audio / peak).astype(np.float32)
    return audio.astype(np.float32)


def process_audio(audio: np.ndarray, sample_rate: int, highpass_cutoff: int = 80) -> np.ndarray:
    """High-pass filter then peak-normalize, ready for transcription."""
    return normalize(highpass(audio, sample_rate, highpass_cutoff))


def load_model(repo: str):
    """Load (and cache) the parakeet-mlx model. Triggers a one-time download."""
    if repo not in _MODEL_CACHE:
        from parakeet_mlx import from_pretrained

        _MODEL_CACHE[repo] = from_pretrained(repo)
    return _MODEL_CACHE[repo]


def is_model_loaded(repo: str) -> bool:
    return repo in _MODEL_CACHE


def transcribe(audio: np.ndarray, model, sample_rate: int) -> str:
    """Transcribe a float32 mono array via parakeet-mlx, returning the text."""
    import tempfile
    from pathlib import Path

    from scipy.io import wavfile

    pcm16 = (np.clip(audio, -1.0, 1.0) * 32767).astype(np.int16)
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as handle:
        path = handle.name
    try:
        wavfile.write(path, sample_rate, pcm16)
        return model.transcribe(path).text.strip()
    finally:
        Path(path).unlink(missing_ok=True)
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_transcriber.py -v`
Expected: PASS (5 tests). (`load_model`/`is_model_loaded`/`transcribe` are exercised manually in Task 8.)

- [ ] **Step 5: Commit**

```bash
git add echopad/transcriber.py tests/test_transcriber.py
git commit -m "feat: parakeet-mlx transcriber with high-pass/normalize preprocessing"
```

---

## Task 4: mic.py AudioRecorder + dictation runner rewrite

**Files:**
- Modify: `echopad/mic.py` (replace `MicStream` with `AudioRecorder`)
- Modify: `echopad/dictation.py` (rewrite `_default_runner`; runner gains `set_state`)
- Test: `tests/test_mic.py` (rewrite), `tests/test_dictation.py` (update runner signatures)

After this task `dictation.py` no longer imports `echopad.stt`.

- [ ] **Step 1: Rewrite `tests/test_mic.py`** (replace the whole file)

```python
import numpy as np
from echopad.mic import AudioRecorder


def test_get_audio_empty_before_recording():
    rec = AudioRecorder(sample_rate=16000)
    audio = rec.get_audio()
    assert isinstance(audio, np.ndarray)
    assert audio.dtype == np.float32
    assert audio.size == 0


def test_get_audio_concatenates_frames():
    rec = AudioRecorder(sample_rate=16000)
    # Simulate two callback blocks of mono float32 frames.
    rec._frames.append(np.array([0.1, 0.2], dtype=np.float32))
    rec._frames.append(np.array([0.3], dtype=np.float32))
    audio = rec.get_audio()
    assert audio.dtype == np.float32
    assert np.allclose(audio, [0.1, 0.2, 0.3])
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_mic.py -v`
Expected: FAIL with `ImportError: cannot import name 'AudioRecorder'`.

- [ ] **Step 3: Replace `echopad/mic.py` entirely with:**

```python
import numpy as np
import sounddevice as sd


class AudioRecorder:
    """Record mono float32 audio at `sample_rate` into memory.

    Use as a context manager: recording runs between __enter__ and __exit__.
    Call get_audio() to get the concatenated float32 array (empty if nothing
    was captured).
    """

    def __init__(self, sample_rate: int = 16000):
        self.sample_rate = sample_rate
        self._frames: list[np.ndarray] = []
        self._stream: sd.InputStream | None = None

    def _callback(self, indata, frames, time_info, status):
        self._frames.append(indata[:, 0].copy())

    def __enter__(self) -> "AudioRecorder":
        self._frames = []
        self._stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype="float32",
            callback=self._callback,
        )
        self._stream.start()
        return self

    def get_audio(self) -> np.ndarray:
        if not self._frames:
            return np.zeros(0, dtype=np.float32)
        return np.concatenate(self._frames).astype(np.float32)

    def __exit__(self, *exc) -> None:
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
```

- [ ] **Step 4: Update `tests/test_dictation.py`** — the runner is now called with a 4th arg `set_state`. Replace the whole file with:

```python
import threading
import time

from echopad.config import load_config
from echopad.dictation import DictationController


def _cfg():
    return load_config(
        config_path=None,
        env={"ELEVENLABS_API_KEY": "el", "MINIMAX_API_KEY": "mm"},
    )


def test_toggle_starts_then_stops():
    started = threading.Event()

    def fake_runner(config, stop_event, on_committed, set_state):
        started.set()
        stop_event.wait()

    ctrl = DictationController(_cfg(), paste=lambda _t: None, runner=fake_runner)

    assert ctrl.is_running() is False
    ctrl.toggle()
    assert started.wait(timeout=1.0)
    assert ctrl.is_running() is True

    ctrl.toggle()
    for _ in range(50):
        if not ctrl.is_running():
            break
        time.sleep(0.02)
    assert ctrl.is_running() is False


def test_committed_text_is_pasted_with_trailing_space():
    pasted = []

    def fake_runner(config, stop_event, on_committed, set_state):
        on_committed("hello world")
        stop_event.wait()

    ctrl = DictationController(_cfg(), paste=pasted.append, runner=fake_runner)
    ctrl.toggle()
    for _ in range(50):
        if pasted:
            break
        time.sleep(0.02)
    ctrl.toggle()
    assert pasted == ["hello world "]


def test_runner_error_is_surfaced_and_state_reset():
    notes = []
    states = []

    def boom_runner(config, stop_event, on_committed, set_state):
        raise RuntimeError("model boom")

    ctrl = DictationController(
        _cfg(),
        paste=lambda _t: None,
        runner=boom_runner,
        notify=notes.append,
        on_state=states.append,
    )
    ctrl.start()
    for _ in range(50):
        if notes and states:
            break
        time.sleep(0.02)
    assert any("model boom" in n for n in notes)
    assert "idle" in states
```

- [ ] **Step 5: Replace `echopad/dictation.py` entirely with:**

```python
import threading
from typing import Callable

from echopad.config import Config
from echopad.mic import AudioRecorder
from echopad.transcriber import is_model_loaded, load_model, process_audio, transcribe

PasteFn = Callable[[str], None]
NotifyFn = Callable[[str], None]
StateFn = Callable[[str], None]
Runner = Callable[..., None]  # (config, stop_event, on_committed, set_state)


def _default_runner(config, stop_event, on_committed, set_state) -> None:
    """Record while stop_event is unset, then transcribe locally and emit text."""
    if not is_model_loaded(config.stt_model_repo):
        raise RuntimeError("Speech model is still loading; try again in a moment.")
    model = load_model(config.stt_model_repo)

    with AudioRecorder(sample_rate=config.sample_rate) as recorder:
        stop_event.wait()
        audio = recorder.get_audio()

    if audio.size == 0:
        return
    set_state("transcribing")
    processed = process_audio(audio, config.sample_rate, config.stt_highpass_cutoff)
    text = transcribe(processed, model, config.sample_rate)
    if text:
        on_committed(text)


class DictationController:
    """Toggle dictation on/off. Records while on; transcribes & pastes on stop."""

    def __init__(
        self,
        config: Config,
        paste: PasteFn,
        runner: Runner = _default_runner,
        notify: NotifyFn | None = None,
        on_state: StateFn | None = None,
    ):
        self._config = config
        self._paste = paste
        self._runner = runner
        self._notify = notify
        self._on_state = on_state
        self._stop_event: threading.Event | None = None
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def toggle(self) -> None:
        if self.is_running():
            self.stop()
        else:
            self.start()

    def start(self) -> None:
        with self._lock:
            if self.is_running():
                return
            stop_event = threading.Event()
            self._stop_event = stop_event

            def on_committed(text: str) -> None:
                self._paste(text + " ")

            def set_state(state: str) -> None:
                if self._on_state is not None:
                    self._on_state(state)

            def worker() -> None:
                try:
                    self._runner(self._config, stop_event, on_committed, set_state)
                except Exception as exc:
                    if self._notify is not None:
                        self._notify(f"Dictation stopped: {exc}")
                finally:
                    if self._on_state is not None:
                        self._on_state("idle")

            self._thread = threading.Thread(target=worker, daemon=True)
            self._thread.start()
            if self._on_state is not None:
                self._on_state("listening")

    def stop(self) -> None:
        # Signal recording to end; the worker transcribes, pastes, and sets the
        # icon back to idle itself. is_running() stays True until it finishes,
        # which prevents a new recording from overlapping an in-flight transcription.
        with self._lock:
            if self._stop_event is not None:
                self._stop_event.set()
```

- [ ] **Step 6: Run the affected tests**

Run: `pytest tests/test_mic.py tests/test_dictation.py -v`
Expected: PASS (2 mic tests + 3 dictation tests).

- [ ] **Step 7: Run the full suite** (stt.py still present and importable, so test_stt.py still passes)

Run: `pytest -q`
Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add echopad/mic.py echopad/dictation.py tests/test_mic.py tests/test_dictation.py
git commit -m "feat: record-then-transcribe dictation runner (local parakeet)"
```

---

## Task 5: Delete the dead ElevenLabs STT module

**Files:**
- Delete: `echopad/stt.py`, `tests/test_stt.py`

Nothing imports `echopad.stt` anymore (Task 4 removed the last use).

- [ ] **Step 1: Confirm no remaining references**

Run: `grep -rn "echopad.stt\|from echopad import stt\|run_session\|parse_message" echopad tests`
Expected: no matches.

- [ ] **Step 2: Delete the files**

```bash
git rm echopad/stt.py tests/test_stt.py
```

- [ ] **Step 3: Run the full suite**

Run: `pytest -q`
Expected: all pass (now without the STT tests).

- [ ] **Step 4: Commit**

```bash
git commit -m "chore: remove dead ElevenLabs realtime STT module"
```

---

## Task 6: config.py — remove the old ElevenLabs `[stt]` fields

**Files:**
- Modify: `echopad/config.py`
- Test: `tests/test_config.py`

Now unused (stt.py is gone), so drop `stt_model_id`, `stt_language`, `stt_audio_format`.

- [ ] **Step 1: Update `tests/test_config.py`** — remove assertions referencing the deleted fields. In `test_defaults_when_no_toml`, delete these three lines:
```python
    assert cfg.stt_model_id == "scribe_v2_realtime"
    assert cfg.stt_audio_format == "pcm_16000"
    assert cfg.stt_language is None
```
And in `test_toml_overrides_defaults`, delete the line:
```python
    assert cfg.stt_language == "en"
```
and change its TOML setup so it no longer sets `[stt]\nlanguage`. Replace that test's `p.write_text(...)` call with:
```python
    p.write_text(
        '[tts]\nvoice_id = "myvoice"\n'
        '[hotkeys]\ntoggle_dictation = "<ctrl>+d"\n'
    )
```
(Leave the `tts_voice_id`, `hotkeys.toggle_dictation`, and `tts_model_id` assertions in that test as-is.)

- [ ] **Step 2: Remove the fields from `echopad/config.py`**

In the `Config` dataclass, delete these three lines:
```python
    stt_model_id: str
    stt_language: str | None
    stt_audio_format: str
```
In `load_config`, delete the `language = stt.get("language", "") or ""` line, and delete these three keyword arguments from the `Config(...)` call:
```python
        stt_model_id=stt.get("model_id", "scribe_v2_realtime"),
        stt_language=language if language else None,
        stt_audio_format=stt.get("audio_format", "pcm_16000"),
```

- [ ] **Step 3: Run the full suite**

Run: `pytest -q`
Expected: all pass.

- [ ] **Step 4: Commit**

```bash
git add echopad/config.py tests/test_config.py
git commit -m "chore: drop unused ElevenLabs STT config fields"
```

---

## Task 7: app.py — warm-load model, transcribing state, drop manual toggle state

**Files:**
- Modify: `echopad/app.py`

(No unit test — UI/process wiring; verified manually in Task 8.)

- [ ] **Step 1: Add the transcribing icon.** Replace the `_ICONS` line in `echopad/app.py` with:

```python
_ICONS = {"idle": "🎙️", "listening": "🔴", "transcribing": "⏳", "speaking": "🔊"}
```

- [ ] **Step 2: Warm-load the model at startup.** In `EchoPadApp.__init__`, immediately after `self._hotkeys.start()`, add:

```python
        self._model_thread = threading.Thread(target=self._warm_load_model, daemon=True)
        self._model_thread.start()
```
And add `import threading` at the top of the file (below `import queue`).

- [ ] **Step 3: Add the warm-load method.** Add this method to `EchoPadApp` (e.g. right after `_drain_ui`):

```python
    def _warm_load_model(self) -> None:
        from echopad.transcriber import load_model

        try:
            load_model(self._config.stt_model_repo)
        except Exception as exc:
            self._notify(f"Speech model failed to load: {exc}")
```

- [ ] **Step 4: Let the controller drive dictation state.** Replace the `_on_toggle` method with:

```python
    def _on_toggle(self) -> None:
        # The controller/runner drive listening→transcribing→idle via on_state.
        self._dictation.toggle()
```

- [ ] **Step 5: Smoke-test imports** (do NOT run the app)

Run: `python -c "import echopad.app, echopad.__main__; print('ok')"`
Expected: prints `ok`.

- [ ] **Step 6: Run the full suite**

Run: `pytest -q`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add echopad/app.py
git commit -m "feat: warm-load STT model at startup; transcribing menubar state"
```

---

## Task 8: Manual verification + README update

**Files:**
- Modify: `README.md`

Requires the venv from Task 1, Microphone + Accessibility permissions, and audio.

- [ ] **Step 1: Update `README.md` setup** — change the Setup section to reflect local STT. Replace the Setup numbered list with:

```markdown
## Setup
1. `brew install portaudio ffmpeg`
2. `python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`
   (If MLX has no wheel for your Python, use Python 3.12: `python3.12 -m venv .venv`.)
3. `export ELEVENLABS_API_KEY=...` (for TTS; MINIMAX_API_KEY is expected to already be set)
4. `cp config.example.toml ~/.config/echopad/config.toml` and edit the voice id.
5. `python -m echopad` — first launch downloads the parakeet STT model (~0.6–1.2 GB), once.

Dictation runs fully locally (parakeet-mlx). Only speak-selection uses the network.
```

- [ ] **Step 2: Update the dictation part of the manual checklist** in `README.md`. Replace the **Dictation:** block under "Manual verification" with:

```markdown
**Dictation (local parakeet-mlx):**
1. Wait a few seconds after launch for the model to warm-load.
2. Click into a text field (e.g. TextEdit).
3. Press ⌥⌘D — the icon turns 🔴 (recording).
4. Speak a sentence, then press ⌥⌘D again — the icon shows ⏳ while transcribing,
   then the text is pasted and the icon returns to 🎙️.
5. Copy something beforehand and confirm it's still on your clipboard afterward.
6. Toggling on within a second of launch (model not loaded) shows a
   "still loading" notification instead of recording silently.
```

- [ ] **Step 3: Launch and run the checklist**

```bash
cd ~/echopad && source .venv/bin/activate && python -m echopad
```
Walk the Dictation steps above and the existing Speak-selection steps. Confirm: transcription is accurate, paste works, clipboard preserved, ⏳ shows during transcription, empty recording pastes nothing.

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: update setup + manual checklist for local parakeet dictation"
```

---

## Self-Review Notes (addressed)

- **Spec coverage:** engine swap to parakeet (Tasks 1,3,4); paste once on toggle-off (Task 4 `_default_runner`); high-pass/normalize preprocessing kept (Task 3); `mic.py` → float32 AudioRecorder (Task 4); `stt.py`/`test_stt.py` removed (Task 5); config `[stt]` swapped, ELEVENLABS_API_KEY still required (Tasks 2,6); warm-load + transcribing state (Task 7); model-still-loading + empty-recording handling (Task 4 runner); Python 3.14 risk spike + model-download risk (Task 1). All covered.
- **Green at every commit:** new config fields added before old removed; `stt.py` deleted only after Task 4 drops its last import; old config fields removed only after `stt.py` is gone.
- **No placeholders:** every code/test step has complete content.
- **Type consistency:** `Config.stt_model_repo`/`stt_highpass_cutoff`/`sample_rate`, `transcriber.{highpass,normalize,process_audio,load_model,is_model_loaded,transcribe}`, `mic.AudioRecorder.get_audio`, and the 4-arg Runner `(config, stop_event, on_committed, set_state)` are used consistently across Tasks 2–7.
```

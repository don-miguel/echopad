import threading

import numpy as np
from echopad import transcriber
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


class _FakeModel:
    def transcribe(self, path):
        _FakeModel.thread_id = threading.get_ident()

        class _Result:
            text = "ok"

        return _Result()


def test_transcribe_runs_on_one_dedicated_thread():
    # Regression: MLX models are thread-bound. All transcription must run on a
    # single dedicated thread (not the caller's), so it matches the load thread
    # and never hits "There is no Stream(gpu, 0) in current thread".
    audio = np.zeros(1600, dtype=np.float32)
    main_id = threading.get_ident()

    transcriber.transcribe(audio, _FakeModel(), 16000)
    first = _FakeModel.thread_id
    transcriber.transcribe(audio, _FakeModel(), 16000)
    second = _FakeModel.thread_id

    assert first != main_id  # offloaded to the dedicated MLX thread
    assert first == second  # same dedicated thread every time

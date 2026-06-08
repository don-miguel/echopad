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

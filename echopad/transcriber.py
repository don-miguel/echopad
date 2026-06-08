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

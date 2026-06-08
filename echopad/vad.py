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

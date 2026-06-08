import queue

import numpy as np
import sounddevice as sd


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

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

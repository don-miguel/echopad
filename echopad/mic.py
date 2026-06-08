import queue

import sounddevice as sd


class MicStream:
    """Capture mono 16-bit PCM from the default input as raw byte blocks.

    Use as a context manager; call `read()` to get the next block of PCM bytes.
    """

    def __init__(self, sample_rate: int = 16000, block_ms: int = 100):
        self.sample_rate = sample_rate
        self.blocksize = int(sample_rate * block_ms / 1000)
        self._frames: "queue.Queue[bytes]" = queue.Queue()
        self._stream: sd.RawInputStream | None = None

    def _callback(self, indata, frames, time_info, status):
        # indata is a bytes-like buffer because dtype="int16" on a RawInputStream
        self._frames.put(bytes(indata))

    def __enter__(self) -> "MicStream":
        self._stream = sd.RawInputStream(
            samplerate=self.sample_rate,
            blocksize=self.blocksize,
            dtype="int16",
            channels=1,
            callback=self._callback,
        )
        self._stream.start()
        return self

    def read(self, timeout: float | None = None) -> bytes | None:
        """Return the next PCM block, or None if none arrived within `timeout`."""
        try:
            return self._frames.get(timeout=timeout)
        except queue.Empty:
            return None

    def __exit__(self, *exc) -> None:
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None

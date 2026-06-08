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

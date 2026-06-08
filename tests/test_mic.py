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

import numpy as np
from echopad.vad import frame_to_pcm16_bytes, Segmenter


def _f(value, n=4):
    return np.full(n, value, dtype=np.float32)


def test_frame_to_pcm16_bytes_length_and_encoding():
    frame = np.array([0.0, 1.0, -1.0], dtype=np.float32)
    data = frame_to_pcm16_bytes(frame)
    assert len(data) == 3 * 2  # int16 = 2 bytes/sample
    decoded = np.frombuffer(data, dtype="<i2")
    assert decoded[0] == 0
    assert decoded[1] == 32767
    assert decoded[2] == -32767


def test_emits_segment_after_pause():
    seg = Segmenter(pause_frames=3)
    assert seg.push(True, _f(1.0)) is None   # speech
    assert seg.push(True, _f(1.0)) is None   # speech
    assert seg.push(False, _f(0.0)) is None  # silence 1
    assert seg.push(False, _f(0.0)) is None  # silence 2
    out = seg.push(False, _f(0.0))           # silence 3 -> pause reached
    assert out is not None
    assert 1.0 in out                        # contains the speech


def test_brief_silence_does_not_split():
    seg = Segmenter(pause_frames=3)
    seg.push(True, _f(1.0))
    assert seg.push(False, _f(0.0)) is None   # silence 1 (< pause)
    assert seg.push(False, _f(0.0)) is None   # silence 2 (< pause)
    assert seg.push(True, _f(2.0)) is None    # speech resumes -> no split
    seg.push(False, _f(0.0))
    seg.push(False, _f(0.0))
    out = seg.push(False, _f(0.0))            # now 3 in a row
    assert out is not None
    assert 1.0 in out and 2.0 in out          # single segment spans both


def test_two_utterances_emit_two_segments():
    seg = Segmenter(pause_frames=2)
    seg.push(True, _f(1.0))
    seg.push(False, _f(0.0))
    a = seg.push(False, _f(0.0))
    seg.push(True, _f(2.0))
    seg.push(False, _f(0.0))
    b = seg.push(False, _f(0.0))
    assert a is not None and 1.0 in a
    assert b is not None and 2.0 in b


def test_flush_returns_trailing_speech_then_none():
    seg = Segmenter(pause_frames=3)
    seg.push(True, _f(5.0))
    seg.push(True, _f(5.0))
    out = seg.flush()
    assert out is not None and 5.0 in out
    assert seg.flush() is None                # nothing left


def test_silence_before_speech_ignored():
    seg = Segmenter(pause_frames=2)
    assert seg.push(False, _f(0.0)) is None
    assert seg.push(False, _f(0.0)) is None
    assert seg.flush() is None

from echopad.mic import MicStream


def test_read_returns_none_on_timeout():
    # No stream started, so the frame queue stays empty: read must time out to
    # None rather than raising queue.Empty (which would crash the pump loop).
    mic = MicStream()
    assert mic.read(timeout=0.01) is None

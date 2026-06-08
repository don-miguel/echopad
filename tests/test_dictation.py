import threading
import time

from echopad.config import load_config
from echopad.dictation import DictationController


def _cfg():
    return load_config(
        config_path=None,
        env={"ELEVENLABS_API_KEY": "el", "MINIMAX_API_KEY": "mm"},
    )


def test_toggle_starts_then_stops():
    started = threading.Event()

    def fake_runner(config, stop_event, on_committed, set_state):
        started.set()
        stop_event.wait()

    ctrl = DictationController(_cfg(), paste=lambda _t: None, runner=fake_runner)

    assert ctrl.is_running() is False
    ctrl.toggle()
    assert started.wait(timeout=1.0)
    assert ctrl.is_running() is True

    ctrl.toggle()
    for _ in range(50):
        if not ctrl.is_running():
            break
        time.sleep(0.02)
    assert ctrl.is_running() is False


def test_committed_text_is_pasted_with_trailing_space():
    pasted = []

    def fake_runner(config, stop_event, on_committed, set_state):
        on_committed("hello world")
        stop_event.wait()

    ctrl = DictationController(_cfg(), paste=pasted.append, runner=fake_runner)
    ctrl.toggle()
    for _ in range(50):
        if pasted:
            break
        time.sleep(0.02)
    ctrl.toggle()
    assert pasted == ["hello world "]


def test_runner_error_is_surfaced_and_state_reset():
    notes = []
    states = []

    def boom_runner(config, stop_event, on_committed, set_state):
        raise RuntimeError("model boom")

    ctrl = DictationController(
        _cfg(),
        paste=lambda _t: None,
        runner=boom_runner,
        notify=notes.append,
        on_state=states.append,
    )
    ctrl.start()
    for _ in range(50):
        if notes and states:
            break
        time.sleep(0.02)
    assert any("model boom" in n for n in notes)
    assert "idle" in states

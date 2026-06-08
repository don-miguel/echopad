import time

from echopad.config import load_config
from echopad.speak_selection import SpeakSelectionController


def _cfg():
    return load_config(
        config_path=None,
        env={"ELEVENLABS_API_KEY": "el", "MINIMAX_API_KEY": "mm"},
    )


class FakePlayer:
    def __init__(self):
        self.spoken = []
        self.stopped = False

    def speak(self, text):
        self.spoken.append(text)

    def stop(self):
        self.stopped = True


def _wait(predicate, timeout=1.0):
    for _ in range(int(timeout / 0.02)):
        if predicate():
            return True
        time.sleep(0.02)
    return predicate()


def test_trigger_summarizes_then_speaks():
    player = FakePlayer()
    notes = []
    ctrl = SpeakSelectionController(
        _cfg(),
        tts_player=player,
        capture=lambda: "a long piece of selected text",
        summarize_fn=lambda text, cfg: "SHORT SUMMARY",
        notify=notes.append,
    )
    ctrl.trigger()
    assert _wait(lambda: player.spoken == ["SHORT SUMMARY"])
    assert notes == []


def test_trigger_with_empty_selection_notifies_and_skips():
    player = FakePlayer()
    notes = []
    called = []
    ctrl = SpeakSelectionController(
        _cfg(),
        tts_player=player,
        capture=lambda: "   ",
        summarize_fn=lambda text, cfg: called.append(text) or "x",
        notify=notes.append,
    )
    ctrl.trigger()
    time.sleep(0.1)
    assert player.spoken == []
    assert called == []
    assert notes and "selected" in notes[0].lower()


def test_state_callbacks_wrap_playback():
    player = FakePlayer()
    states = []
    ctrl = SpeakSelectionController(
        _cfg(),
        tts_player=player,
        capture=lambda: "a long piece of selected text",
        summarize_fn=lambda text, cfg: "SHORT SUMMARY",
        notify=lambda _m: None,
        on_state=states.append,
    )
    ctrl.trigger()
    assert _wait(lambda: states == ["speaking", "idle"])
    assert player.spoken == ["SHORT SUMMARY"]


def test_trigger_without_keys_notifies_and_skips():
    cfg = load_config(config_path=None, env={})  # no API keys
    player = FakePlayer()
    notes = []
    summarized = []
    ctrl = SpeakSelectionController(
        cfg,
        tts_player=player,
        capture=lambda: "some selected text",
        summarize_fn=lambda t, c: summarized.append(t) or "x",
        notify=notes.append,
    )
    ctrl.trigger()
    time.sleep(0.1)
    assert player.spoken == []
    assert summarized == []
    assert notes and ("MINIMAX_API_KEY" in notes[0] or "ELEVENLABS_API_KEY" in notes[0])


def test_stop_forwards_to_player():
    player = FakePlayer()
    ctrl = SpeakSelectionController(
        _cfg(),
        tts_player=player,
        capture=lambda: "text",
        summarize_fn=lambda text, cfg: "s",
        notify=lambda _m: None,
    )
    ctrl.stop()
    assert player.stopped is True

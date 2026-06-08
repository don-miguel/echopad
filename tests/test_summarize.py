import pytest
from echopad.config import load_config
from echopad.summarize import summarize, build_messages


def _cfg():
    return load_config(
        config_path=None,
        env={"ELEVENLABS_API_KEY": "el", "MINIMAX_API_KEY": "mm"},
    )


class FakeMessage:
    def __init__(self, content):
        self.content = content


class FakeChoice:
    def __init__(self, content):
        self.message = FakeMessage(content)


class FakeResponse:
    def __init__(self, content):
        self.choices = [FakeChoice(content)]


class FakeCompletions:
    def __init__(self, content):
        self._content = content
        self.last_kwargs = None

    def create(self, **kwargs):
        self.last_kwargs = kwargs
        return FakeResponse(self._content)


class FakeChat:
    def __init__(self, content):
        self.completions = FakeCompletions(content)


class FakeClient:
    def __init__(self, content):
        self.chat = FakeChat(content)


def test_build_messages_includes_style_and_text():
    msgs = build_messages("the body text", "Be terse.")
    assert msgs[0]["role"] == "system"
    assert "Be terse." in msgs[0]["content"]
    assert msgs[1] == {"role": "user", "content": "the body text"}


def test_summarize_returns_model_content_and_uses_config_model():
    client = FakeClient("  a short summary  ")
    result = summarize("some long text", _cfg(), client=client)
    assert result == "a short summary"
    assert client.chat.completions.last_kwargs["model"] == "MiniMax-M3"


def test_summarize_empty_text_raises():
    with pytest.raises(ValueError):
        summarize("   ", _cfg(), client=FakeClient("x"))


def test_summarize_strips_reasoning_think_block():
    # MiniMax M3 is a reasoning model: it inlines chain-of-thought in a
    # <think>...</think> block before the answer. Only the answer should be spoken.
    content = (
        "<think>\nThe user wants a 2-3 sentence summary. Key points: a, b, c. "
        "Let me write it concisely.\n</think>\n"
        "The board approved hiring and revenue grew eighteen percent."
    )
    result = summarize("some long text", _cfg(), client=FakeClient(content))
    assert result == "The board approved hiring and revenue grew eighteen percent."
    assert "<think>" not in result
    assert "user wants" not in result


def test_summarize_without_think_block_passes_through():
    result = summarize("text", _cfg(), client=FakeClient("  Just the summary.  "))
    assert result == "Just the summary."

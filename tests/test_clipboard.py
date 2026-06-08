from echopad.clipboard import ClipboardBackend, paste_text, capture_selection


class FakeBoard:
    """In-memory clipboard. send_copy/send_paste simulate the OS effect."""

    def __init__(self, initial="", selection="SELECTED"):
        self.value = initial
        self.selection = selection
        self.pasted_value = None  # what was on the clipboard at paste time

    def backend(self):
        return ClipboardBackend(
            get=lambda: self.value,
            set=self._set,
            send_paste=self._paste,
            send_copy=self._copy,
            sleep=lambda _s: None,
        )

    def _set(self, v):
        self.value = v

    def _paste(self):
        self.pasted_value = self.value

    def _copy(self):
        self.value = self.selection


def test_paste_text_pastes_value_and_restores_clipboard():
    fb = FakeBoard(initial="ORIGINAL")
    paste_text("hello world", fb.backend())
    assert fb.pasted_value == "hello world"
    assert fb.value == "ORIGINAL"


def test_capture_selection_returns_selection_and_restores_clipboard():
    fb = FakeBoard(initial="ORIGINAL", selection="the selected text")
    result = capture_selection(fb.backend())
    assert result == "the selected text"
    assert fb.value == "ORIGINAL"


def test_capture_selection_empty_when_nothing_selected():
    fb = FakeBoard(initial="ORIGINAL", selection="")
    result = capture_selection(fb.backend())
    assert result == ""
    assert fb.value == "ORIGINAL"

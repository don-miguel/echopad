import threading
from typing import Callable

from echopad.config import Config

CaptureFn = Callable[[], str]
SummarizeFn = Callable[[str, Config], str]
NotifyFn = Callable[[str], None]
StateFn = Callable[[str], None]


class SpeakSelectionController:
    """Capture the current selection, summarize it, and speak the summary."""

    def __init__(
        self,
        config: Config,
        tts_player,
        capture: CaptureFn,
        summarize_fn: SummarizeFn,
        notify: NotifyFn,
        on_state: StateFn | None = None,
    ):
        self._config = config
        self._player = tts_player
        self._capture = capture
        self._summarize = summarize_fn
        self._notify = notify
        self._on_state = on_state

    def trigger(self) -> None:
        text = self._capture()
        if not text.strip():
            self._notify("Nothing selected")
            return
        threading.Thread(target=self._run, args=(text,), daemon=True).start()

    def _run(self, text: str) -> None:
        try:
            summary = self._summarize(text, self._config)
        except Exception as exc:  # surface, do not silently swallow
            self._notify(f"Summarize failed: {exc}")
            return
        if self._on_state is not None:
            self._on_state("speaking")
        try:
            self._player.speak(summary)
        finally:
            if self._on_state is not None:
                self._on_state("idle")

    def stop(self) -> None:
        self._player.stop()

import threading
from typing import Callable

from echopad.config import Config
from echopad.mic import AudioRecorder
from echopad.transcriber import is_model_loaded, load_model, process_audio, transcribe

PasteFn = Callable[[str], None]
NotifyFn = Callable[[str], None]
StateFn = Callable[[str], None]
Runner = Callable[..., None]  # (config, stop_event, on_committed, set_state)


def _default_runner(config, stop_event, on_committed, set_state) -> None:
    """Record while stop_event is unset, then transcribe locally and emit text."""
    if not is_model_loaded(config.stt_model_repo):
        raise RuntimeError("Speech model is still loading; try again in a moment.")
    model = load_model(config.stt_model_repo)

    with AudioRecorder(sample_rate=config.sample_rate) as recorder:
        stop_event.wait()
        audio = recorder.get_audio()

    if audio.size == 0:
        return
    set_state("transcribing")
    processed = process_audio(audio, config.sample_rate, config.stt_highpass_cutoff)
    text = transcribe(processed, model, config.sample_rate)
    if text:
        on_committed(text)


class DictationController:
    """Toggle dictation on/off. Records while on; transcribes & pastes on stop."""

    def __init__(
        self,
        config: Config,
        paste: PasteFn,
        runner: Runner = _default_runner,
        notify: NotifyFn | None = None,
        on_state: StateFn | None = None,
    ):
        self._config = config
        self._paste = paste
        self._runner = runner
        self._notify = notify
        self._on_state = on_state
        self._stop_event: threading.Event | None = None
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def toggle(self) -> None:
        if self.is_running():
            self.stop()
        else:
            self.start()

    def start(self) -> None:
        with self._lock:
            if self.is_running():
                return
            stop_event = threading.Event()
            self._stop_event = stop_event

            def on_committed(text: str) -> None:
                self._paste(text + " ")

            def set_state(state: str) -> None:
                if self._on_state is not None:
                    self._on_state(state)

            def worker() -> None:
                try:
                    self._runner(self._config, stop_event, on_committed, set_state)
                except Exception as exc:
                    if self._notify is not None:
                        self._notify(f"Dictation stopped: {exc}")
                finally:
                    if self._on_state is not None:
                        self._on_state("idle")

            self._thread = threading.Thread(target=worker, daemon=True)
            self._thread.start()
            if self._on_state is not None:
                self._on_state("listening")

    def stop(self) -> None:
        # Signal recording to end; the worker transcribes, pastes, and sets the
        # icon back to idle itself. is_running() stays True until it finishes,
        # which prevents a new recording from overlapping an in-flight transcription.
        with self._lock:
            if self._stop_event is not None:
                self._stop_event.set()

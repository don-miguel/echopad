import logging
import queue
import threading
import time

import rumps

log = logging.getLogger("echopad")

from echopad.config import Config
from echopad.clipboard import macos_backend, paste_text, capture_selection
from echopad.dictation import DictationController
from echopad.hotkeys import HotkeyManager
from echopad.speak_selection import SpeakSelectionController
from echopad.summarize import summarize
from echopad.tts import TTSPlayer

_ICONS = {"idle": "🎙️", "listening": "🔴", "transcribing": "⏳", "speaking": "🔊"}


class EchoPadApp(rumps.App):
    def __init__(self, config: Config):
        super().__init__("EchoPad", title=_ICONS["idle"])
        self._config = config
        self._backend = macos_backend()

        # UI updates can be requested from background/listener threads; rumps is
        # only safe on the main thread, so everything is funneled through this
        # queue and applied by a Timer that fires on the main run loop.
        self._ui_queue: "queue.Queue" = queue.Queue()

        self._dictation = DictationController(
            config,
            paste=lambda text: paste_text(text, self._backend),
            notify=self._notify,
            on_state=self._set_state,
        )
        self._tts = TTSPlayer(config)
        self._speak = SpeakSelectionController(
            config,
            tts_player=self._tts,
            capture=lambda: capture_selection(self._backend),
            summarize_fn=summarize,
            notify=self._notify,
            on_state=self._set_state,
        )

        self.menu = ["Toggle Dictation", "Speak Selection", "Stop"]

        self._ui_timer = rumps.Timer(self._drain_ui, 0.1)
        self._ui_timer.start()

        self._hotkeys = HotkeyManager(
            {
                config.hotkeys.toggle_dictation: self._on_toggle,
                config.hotkeys.speak_selection: self._on_speak,
                config.hotkeys.stop: self._on_stop,
            }
        )
        self._hotkeys.start()

        self._model_thread = threading.Thread(target=self._warm_load_model, daemon=True)
        self._model_thread.start()

    # --- main-thread UI marshalling -------------------------------------

    def _post(self, fn) -> None:
        self._ui_queue.put(fn)

    def _drain_ui(self, _timer) -> None:
        while True:
            try:
                fn = self._ui_queue.get_nowait()
            except queue.Empty:
                return
            fn()

    def _warm_load_model(self) -> None:
        from echopad.transcriber import load_model

        log.info(
            "Loading speech model %s (first run downloads ~1 GB)…",
            self._config.stt_model_repo,
        )
        start = time.monotonic()
        try:
            load_model(self._config.stt_model_repo)
        except Exception as exc:
            log.error("Speech model failed to load: %s", exc)
            self._notify(f"Speech model failed to load: {exc}")
            return
        log.info(
            "Speech model ready in %.1fs — dictation available.",
            time.monotonic() - start,
        )

    def _set_state(self, state: str) -> None:
        self._post(lambda: setattr(self, "title", _ICONS[state]))

    def _notify(self, message: str) -> None:
        self._post(lambda: rumps.notification("EchoPad", "", message))

    # --- actions ---------------------------------------------------------

    def _on_toggle(self) -> None:
        # The controller/runner drive listening→transcribing→idle via on_state.
        self._dictation.toggle()

    def _on_speak(self) -> None:
        # The controller drives "speaking"/"idle" state around playback.
        self._speak.trigger()

    def _on_stop(self) -> None:
        self._speak.stop()
        if not self._dictation.is_running():
            self._set_state("idle")

    @rumps.clicked("Toggle Dictation")
    def _menu_toggle(self, _sender):
        self._on_toggle()

    @rumps.clicked("Speak Selection")
    def _menu_speak(self, _sender):
        self._on_speak()

    @rumps.clicked("Stop")
    def _menu_stop(self, _sender):
        self._on_stop()

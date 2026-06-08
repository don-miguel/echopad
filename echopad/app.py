import queue

import rumps

from echopad.config import Config
from echopad.clipboard import macos_backend, paste_text, capture_selection
from echopad.dictation import DictationController
from echopad.hotkeys import HotkeyManager
from echopad.speak_selection import SpeakSelectionController
from echopad.summarize import summarize
from echopad.tts import TTSPlayer

_ICONS = {"idle": "🎙️", "listening": "🔴", "speaking": "🔊"}


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

    def _set_state(self, state: str) -> None:
        self._post(lambda: setattr(self, "title", _ICONS[state]))

    def _notify(self, message: str) -> None:
        self._post(lambda: rumps.notification("EchoPad", "", message))

    # --- actions ---------------------------------------------------------

    def _on_toggle(self) -> None:
        self._dictation.toggle()
        self._set_state("listening" if self._dictation.is_running() else "idle")

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

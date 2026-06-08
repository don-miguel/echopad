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

        self._dictation = DictationController(
            config,
            paste=lambda text: paste_text(text, self._backend),
        )
        self._tts = TTSPlayer(config)
        self._speak = SpeakSelectionController(
            config,
            tts_player=self._tts,
            capture=lambda: capture_selection(self._backend),
            summarize_fn=summarize,
            notify=self._notify,
        )

        self.menu = ["Toggle Dictation", "Speak Selection", "Stop"]

        self._hotkeys = HotkeyManager(
            {
                config.hotkeys.toggle_dictation: self._on_toggle,
                config.hotkeys.speak_selection: self._on_speak,
                config.hotkeys.stop: self._on_stop,
            }
        )
        self._hotkeys.start()

    def _set_state(self, state: str) -> None:
        self.title = _ICONS[state]

    def _notify(self, message: str) -> None:
        rumps.notification("EchoPad", "", message)

    def _on_toggle(self) -> None:
        self._dictation.toggle()
        self._set_state("listening" if self._dictation.is_running() else "idle")

    def _on_speak(self) -> None:
        self._set_state("speaking")
        self._speak.trigger()

    def _on_stop(self) -> None:
        self._speak.stop()
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

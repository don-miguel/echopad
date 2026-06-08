import logging
import subprocess
from pathlib import Path

from echopad.app import EchoPadApp
from echopad.config import load_config

log = logging.getLogger("echopad")

_ACCESSIBILITY_PANE = (
    "x-apple.systempreferences:com.apple.preference.security"
    "?Privacy_Accessibility"
)


def _accessibility_trusted() -> bool:
    from ApplicationServices import AXIsProcessTrusted

    return bool(AXIsProcessTrusted())


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s echopad: %(message)s",
        datefmt="%H:%M:%S",
    )
    # Quiet noisy third-party INFO logs (HF download chatter, HTTP traces).
    for noisy in ("httpx", "httpcore", "huggingface_hub", "urllib3", "filelock"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    config_path = Path.home() / ".config" / "echopad" / "config.toml"
    config = load_config(config_path=config_path)

    speak_ready = bool(config.minimax_api_key and config.elevenlabs_api_key)
    log.info("Starting EchoPad. Dictation: local (no API key needed).")
    log.info(
        "Speak-selection: %s",
        "enabled" if speak_ready else "disabled — set MINIMAX_API_KEY + ELEVENLABS_API_KEY",
    )

    if not _accessibility_trusted():
        log.warning(
            "Accessibility NOT granted — global hotkeys and paste won't work until "
            "you grant it (System Settings → Privacy & Security → Accessibility) and "
            "restart EchoPad. Opening that pane now."
        )
        subprocess.run(["open", _ACCESSIBILITY_PANE])

    log.info(
        "Menubar ready. Hotkeys: %s = dictation, %s = speak-selection, %s = stop.",
        config.hotkeys.toggle_dictation,
        config.hotkeys.speak_selection,
        config.hotkeys.stop,
    )
    EchoPadApp(config).run()


if __name__ == "__main__":
    main()

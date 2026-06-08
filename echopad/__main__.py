import subprocess
import sys
from pathlib import Path

from echopad.app import EchoPadApp
from echopad.config import load_config

_ACCESSIBILITY_PANE = (
    "x-apple.systempreferences:com.apple.preference.security"
    "?Privacy_Accessibility"
)


def _accessibility_trusted() -> bool:
    from ApplicationServices import AXIsProcessTrusted

    return bool(AXIsProcessTrusted())


def main() -> None:
    config_path = Path.home() / ".config" / "echopad" / "config.toml"
    config = load_config(config_path=config_path)

    if not _accessibility_trusted():
        print(
            "EchoPad needs Accessibility permission for global hotkeys and paste.\n"
            "Opening System Settings → Privacy & Security → Accessibility.\n"
            "Grant it to your terminal/app, then restart EchoPad.",
            file=sys.stderr,
        )
        subprocess.run(["open", _ACCESSIBILITY_PANE])

    EchoPadApp(config).run()


if __name__ == "__main__":
    main()

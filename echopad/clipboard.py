import subprocess
import time
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class ClipboardBackend:
    get: Callable[[], str]
    set: Callable[[str], None]
    send_paste: Callable[[], None]
    send_copy: Callable[[], None]
    sleep: Callable[[float], None]


def paste_text(text: str, backend: ClipboardBackend, restore_delay: float = 0.1) -> None:
    saved = backend.get()
    backend.set(text)
    backend.send_paste()
    backend.sleep(restore_delay)
    backend.set(saved)


def capture_selection(backend: ClipboardBackend, copy_delay: float = 0.1) -> str:
    saved = backend.get()
    backend.set("")  # sentinel: if nothing is selected, Cmd+C won't change it
    backend.send_copy()
    backend.sleep(copy_delay)
    selected = backend.get()
    backend.set(saved)
    return selected


def macos_backend() -> ClipboardBackend:
    """Real backend: pbcopy/pbpaste for the clipboard, pynput for Cmd+C / Cmd+V."""
    from pynput.keyboard import Controller, Key

    keyboard = Controller()

    def get() -> str:
        return subprocess.run(
            ["pbpaste"], capture_output=True, text=True
        ).stdout

    def set_(value: str) -> None:
        subprocess.run(["pbcopy"], input=value, text=True)

    def _cmd(letter: str) -> None:
        with keyboard.pressed(Key.cmd):
            keyboard.press(letter)
            keyboard.release(letter)

    return ClipboardBackend(
        get=get,
        set=set_,
        send_paste=lambda: _cmd("v"),
        send_copy=lambda: _cmd("c"),
        sleep=time.sleep,
    )

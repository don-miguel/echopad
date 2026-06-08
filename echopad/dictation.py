import asyncio
import threading
from typing import Callable

from echopad.config import Config
from echopad.mic import MicStream
from echopad.stt import run_session

PasteFn = Callable[[str], None]
Runner = Callable[[Config, threading.Event, Callable[[str], None]], None]


def _default_runner(
    config: Config,
    stop_event: threading.Event,
    on_committed: Callable[[str], None],
) -> None:
    """Capture mic audio and stream it to STT until stop_event is set."""

    async def main() -> None:
        audio_queue: "asyncio.Queue[bytes | None]" = asyncio.Queue()
        loop = asyncio.get_running_loop()

        async def pump_mic() -> None:
            with MicStream(sample_rate=config.sample_rate) as mic:
                while not stop_event.is_set():
                    chunk = await loop.run_in_executor(None, mic.read, 0.2)
                    if chunk is not None:
                        await audio_queue.put(chunk)
            await audio_queue.put(None)

        await asyncio.gather(
            pump_mic(),
            run_session(config, audio_queue, on_committed),
        )

    asyncio.run(main())


class DictationController:
    """Toggle dictation on/off. While on, committed transcripts are pasted."""

    def __init__(self, config: Config, paste: PasteFn, runner: Runner = _default_runner):
        self._config = config
        self._paste = paste
        self._runner = runner
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

            def worker() -> None:
                self._runner(self._config, stop_event, on_committed)

            self._thread = threading.Thread(target=worker, daemon=True)
            self._thread.start()

    def stop(self) -> None:
        with self._lock:
            if self._stop_event is not None:
                self._stop_event.set()
            thread = self._thread
        if thread is not None:
            thread.join(timeout=3.0)
        self._thread = None
        self._stop_event = None

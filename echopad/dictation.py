import asyncio
import threading
from typing import Callable

from echopad.config import Config
from echopad.mic import MicStream
from echopad.stt import run_session

PasteFn = Callable[[str], None]
NotifyFn = Callable[[str], None]
StateFn = Callable[[str], None]
Runner = Callable[[Config, threading.Event, Callable[[str], None]], None]


def _default_runner(
    config: Config,
    stop_event: threading.Event,
    on_committed: Callable[[str], None],
) -> None:
    """Capture mic audio and stream it to STT until stop_event is set.

    Raises if the STT session fails (e.g. a WebSocket/auth error) so the caller
    can surface it instead of dying silently.
    """

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

        pump = asyncio.create_task(pump_mic())
        session = asyncio.create_task(run_session(config, audio_queue, on_committed))
        done, pending = await asyncio.wait(
            {pump, session}, return_when=asyncio.FIRST_COMPLETED
        )
        # Whichever finished first, tear the other down cleanly.
        stop_event.set()
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
        for task in done:
            exc = task.exception()
            if exc is not None:
                raise exc

    asyncio.run(main())


class DictationController:
    """Toggle dictation on/off. While on, committed transcripts are pasted."""

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

            def worker() -> None:
                try:
                    self._runner(self._config, stop_event, on_committed)
                except Exception as exc:
                    if self._notify is not None:
                        self._notify(f"Dictation stopped: {exc}")
                finally:
                    # Reflect that capture has ended (covers crashes, not just
                    # a user-initiated stop).
                    if self._on_state is not None:
                        self._on_state("idle")

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

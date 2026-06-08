import asyncio
import base64
import json
from typing import Callable

from echopad.config import Config

STT_URL = "wss://api.elevenlabs.io/v1/speech-to-text/realtime"

_COMMITTED = {"committed_transcript", "committed_transcript_with_timestamps"}
_ERRORS = {
    "error",
    "auth_error",
    "quota_exceeded",
    "rate_limited",
    "session_time_limit_exceeded",
}


def parse_message(raw: str) -> tuple[str | None, str | None]:
    """Map a server frame to (kind, text). kind in {committed, partial, error, None}."""
    msg = json.loads(raw)
    mt = msg.get("message_type")
    if mt in _COMMITTED:
        return ("committed", msg.get("text", ""))
    if mt == "partial_transcript":
        return ("partial", msg.get("text", ""))
    if mt in _ERRORS:
        return ("error", msg.get("message") or mt)
    return (None, None)


def build_url(config: Config) -> str:
    params = [
        f"model_id={config.stt_model_id}",
        f"audio_format={config.stt_audio_format}",
        "commit_strategy=vad",
    ]
    if config.stt_language:
        params.append(f"language_code={config.stt_language}")
    return STT_URL + "?" + "&".join(params)


def encode_audio_chunk(pcm: bytes, sample_rate: int) -> str:
    return json.dumps(
        {
            "message_type": "input_audio_chunk",
            "audio_base_64": base64.b64encode(pcm).decode("ascii"),
            "commit": False,
            "sample_rate": sample_rate,
        }
    )


async def run_session(
    config: Config,
    audio_queue: "asyncio.Queue[bytes | None]",
    on_committed: Callable[[str], None],
    on_partial: Callable[[str], None] | None = None,
    on_error: Callable[[str], None] | None = None,
) -> None:
    """Open the STT WebSocket, stream audio from the queue, dispatch transcripts.

    Put `None` on `audio_queue` to end the session. Requires `websockets`.
    """
    import websockets

    url = build_url(config)
    headers = {"xi-api-key": config.elevenlabs_api_key}
    async with websockets.connect(url, additional_headers=headers) as ws:

        async def sender():
            while True:
                chunk = await audio_queue.get()
                if chunk is None:
                    return
                await ws.send(encode_audio_chunk(chunk, config.sample_rate))

        async def receiver():
            async for raw in ws:
                kind, text = parse_message(raw)
                if kind == "committed" and text:
                    on_committed(text)
                elif kind == "partial" and on_partial:
                    on_partial(text)
                elif kind == "error":
                    if on_error:
                        on_error(text or "stt error")
                    else:
                        raise RuntimeError(text or "stt error")

        send_task = asyncio.create_task(sender())
        recv_task = asyncio.create_task(receiver())
        done, pending = await asyncio.wait(
            {send_task, recv_task}, return_when=asyncio.FIRST_COMPLETED
        )
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
        for task in done:
            exc = task.exception()
            if exc is not None:
                raise exc

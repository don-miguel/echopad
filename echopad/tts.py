import threading

from echopad.config import Config

TTS_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream"


def build_tts_request(config: Config, text: str) -> tuple[str, dict, dict, dict]:
    url = TTS_URL.format(voice_id=config.tts_voice_id)
    headers = {
        "xi-api-key": config.elevenlabs_api_key,
        "Content-Type": "application/json",
    }
    params = {"output_format": config.tts_output_format}
    body = {"text": text, "model_id": config.tts_model_id}
    return url, headers, params, body


class TTSPlayer:
    """Stream ElevenLabs TTS audio and play it; interruptible via stop()."""

    def __init__(self, config: Config):
        self._config = config
        self._stop = threading.Event()

    def stop(self) -> None:
        self._stop.set()

    def speak(self, text: str) -> None:
        import requests
        import sounddevice as sd

        self._stop.clear()
        url, headers, params, body = build_tts_request(self._config, text)
        with requests.post(
            url, headers=headers, params=params, json=body, stream=True, timeout=30
        ) as response:
            response.raise_for_status()
            with sd.RawOutputStream(
                samplerate=self._config.tts_sample_rate,
                channels=1,
                dtype="int16",
            ) as out:
                for chunk in response.iter_content(chunk_size=4096):
                    if self._stop.is_set():
                        break
                    if chunk:
                        out.write(chunk)

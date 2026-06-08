from echopad.config import load_config
from echopad.tts import build_tts_request


def _cfg():
    return load_config(
        config_path=None,
        env={"ELEVENLABS_API_KEY": "el-key", "MINIMAX_API_KEY": "mm"},
    )


def test_build_tts_request_targets_voice_stream_endpoint():
    url, headers, params, body = build_tts_request(_cfg(), "hello world")
    assert url == (
        "https://api.elevenlabs.io/v1/text-to-speech/"
        "21m00Tcm4TlvDq8ikWAM/stream"
    )
    assert headers["xi-api-key"] == "el-key"
    assert headers["Content-Type"] == "application/json"
    assert params["output_format"] == "pcm_24000"
    assert body["text"] == "hello world"
    assert body["model_id"] == "eleven_flash_v2_5"

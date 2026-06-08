import base64
import json
from echopad.config import load_config
from echopad.stt import parse_message, build_url, encode_audio_chunk


def _cfg(**toml):
    return load_config(
        config_path=None,
        env={"ELEVENLABS_API_KEY": "el", "MINIMAX_API_KEY": "mm"},
    )


def test_parse_committed_transcript():
    raw = json.dumps({"message_type": "committed_transcript", "text": "hello there"})
    assert parse_message(raw) == ("committed", "hello there")


def test_parse_committed_with_timestamps():
    raw = json.dumps(
        {"message_type": "committed_transcript_with_timestamps", "text": "hi", "words": []}
    )
    assert parse_message(raw) == ("committed", "hi")


def test_parse_partial_transcript():
    raw = json.dumps({"message_type": "partial_transcript", "text": "hel"})
    assert parse_message(raw) == ("partial", "hel")


def test_parse_error_message():
    raw = json.dumps({"message_type": "auth_error", "message": "bad key"})
    kind, text = parse_message(raw)
    assert kind == "error"
    assert "bad key" in text


def test_parse_unknown_returns_none():
    raw = json.dumps({"message_type": "session_started", "session_id": "x"})
    assert parse_message(raw) == (None, None)


def test_build_url_without_language():
    url = build_url(_cfg())
    assert url.startswith("wss://api.elevenlabs.io/v1/speech-to-text/realtime?")
    assert "model_id=scribe_v2_realtime" in url
    assert "audio_format=pcm_16000" in url
    assert "commit_strategy=vad" in url
    assert "language_code" not in url


def test_encode_audio_chunk_is_valid_json_and_base64():
    payload = encode_audio_chunk(b"\x01\x02\x03\x04", 16000)
    obj = json.loads(payload)
    assert obj["message_type"] == "input_audio_chunk"
    assert obj["commit"] is False
    assert obj["sample_rate"] == 16000
    assert base64.b64decode(obj["audio_base_64"]) == b"\x01\x02\x03\x04"

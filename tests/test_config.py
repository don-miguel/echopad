import pytest
from echopad.config import load_config, Config, ConfigError


def _env(**overrides):
    base = {"ELEVENLABS_API_KEY": "el-key", "MINIMAX_API_KEY": "mm-key"}
    base.update(overrides)
    return base


def test_missing_elevenlabs_key_fails_fast():
    with pytest.raises(ConfigError) as exc:
        load_config(config_path=None, env={"MINIMAX_API_KEY": "mm-key"})
    assert "ELEVENLABS_API_KEY" in str(exc.value)


def test_missing_minimax_key_fails_fast():
    with pytest.raises(ConfigError) as exc:
        load_config(config_path=None, env={"ELEVENLABS_API_KEY": "el-key"})
    assert "MINIMAX_API_KEY" in str(exc.value)


def test_defaults_when_no_toml():
    cfg = load_config(config_path=None, env=_env())
    assert isinstance(cfg, Config)
    assert cfg.elevenlabs_api_key == "el-key"
    assert cfg.minimax_api_key == "mm-key"
    assert cfg.stt_model_id == "scribe_v2_realtime"
    assert cfg.stt_audio_format == "pcm_16000"
    assert cfg.sample_rate == 16000
    assert cfg.stt_language is None
    assert cfg.summarizer_model == "MiniMax-M3"
    assert cfg.summarizer_base_url == "https://api.minimax.io/v1"
    assert cfg.hotkeys.toggle_dictation == "<cmd>+<alt>+d"
    assert cfg.hotkeys.speak_selection == "<cmd>+<alt>+s"
    assert cfg.hotkeys.stop == "<cmd>+<alt>+."


def test_parakeet_defaults():
    cfg = load_config(config_path=None, env=_env())
    assert cfg.stt_model_repo == "mlx-community/parakeet-tdt-0.6b-v2"
    assert cfg.stt_highpass_cutoff == 80
    assert cfg.sample_rate == 16000


def test_parakeet_toml_overrides(tmp_path):
    p = tmp_path / "config.toml"
    p.write_text('[stt]\nmodel_repo = "mlx-community/other"\nhighpass_cutoff = 120\n')
    cfg = load_config(config_path=p, env=_env())
    assert cfg.stt_model_repo == "mlx-community/other"
    assert cfg.stt_highpass_cutoff == 120


def test_toml_overrides_defaults(tmp_path):
    p = tmp_path / "config.toml"
    p.write_text(
        '[tts]\nvoice_id = "myvoice"\n'
        '[stt]\nlanguage = "en"\n'
        '[hotkeys]\ntoggle_dictation = "<ctrl>+d"\n'
    )
    cfg = load_config(config_path=p, env=_env())
    assert cfg.tts_voice_id == "myvoice"
    assert cfg.stt_language == "en"
    assert cfg.hotkeys.toggle_dictation == "<ctrl>+d"
    assert cfg.tts_model_id == "eleven_flash_v2_5"

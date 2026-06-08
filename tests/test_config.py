from echopad.config import load_config, Config


def _env(**overrides):
    base = {"ELEVENLABS_API_KEY": "el-key", "MINIMAX_API_KEY": "mm-key"}
    base.update(overrides)
    return base


def test_missing_keys_do_not_raise_and_are_none():
    # Local dictation needs no keys; the app must still start without them.
    cfg = load_config(config_path=None, env={})
    assert cfg.elevenlabs_api_key is None
    assert cfg.minimax_api_key is None


def test_keys_loaded_when_present():
    cfg = load_config(config_path=None, env=_env())
    assert cfg.elevenlabs_api_key == "el-key"
    assert cfg.minimax_api_key == "mm-key"


def test_defaults_when_no_toml():
    cfg = load_config(config_path=None, env=_env())
    assert isinstance(cfg, Config)
    assert cfg.elevenlabs_api_key == "el-key"
    assert cfg.minimax_api_key == "mm-key"
    assert cfg.sample_rate == 16000
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
        '[hotkeys]\ntoggle_dictation = "<ctrl>+d"\n'
    )
    cfg = load_config(config_path=p, env=_env())
    assert cfg.tts_voice_id == "myvoice"
    assert cfg.hotkeys.toggle_dictation == "<ctrl>+d"
    assert cfg.tts_model_id == "eleven_flash_v2_5"

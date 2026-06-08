import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


@dataclass(frozen=True)
class Hotkeys:
    toggle_dictation: str
    speak_selection: str
    stop: str


@dataclass(frozen=True)
class Config:
    # Optional: local dictation needs no keys. Speak-selection requires both and
    # fails loudly (with a notification) when invoked without them.
    elevenlabs_api_key: str | None
    minimax_api_key: str | None
    sample_rate: int
    stt_model_repo: str
    stt_highpass_cutoff: int
    tts_voice_id: str
    tts_model_id: str
    tts_output_format: str
    tts_sample_rate: int
    summarizer_model: str
    summarizer_base_url: str
    summary_style: str
    hotkeys: Hotkeys


def load_config(
    config_path: Path | None = None,
    env: Mapping[str, str] | None = None,
) -> Config:
    import os

    env = os.environ if env is None else env

    # Keys are optional at load time. Local dictation needs none; speak-selection
    # validates its keys when triggered (see SpeakSelectionController).
    elevenlabs_api_key = env.get("ELEVENLABS_API_KEY") or None
    minimax_api_key = env.get("MINIMAX_API_KEY") or None

    data: dict = {}
    if config_path is not None and Path(config_path).exists():
        with open(config_path, "rb") as f:
            data = tomllib.load(f)

    stt = data.get("stt", {})
    tts = data.get("tts", {})
    summ = data.get("summarizer", {})
    hk = data.get("hotkeys", {})

    return Config(
        elevenlabs_api_key=elevenlabs_api_key,
        minimax_api_key=minimax_api_key,
        sample_rate=int(stt.get("sample_rate", 16000)),
        stt_model_repo=stt.get("model_repo", "mlx-community/parakeet-tdt-0.6b-v2"),
        stt_highpass_cutoff=int(stt.get("highpass_cutoff", 80)),
        tts_voice_id=tts.get("voice_id", "21m00Tcm4TlvDq8ikWAM"),
        tts_model_id=tts.get("model_id", "eleven_flash_v2_5"),
        tts_output_format=tts.get("output_format", "pcm_24000"),
        tts_sample_rate=int(tts.get("sample_rate", 24000)),
        summarizer_model=summ.get("model", "MiniMax-M3"),
        summarizer_base_url=summ.get("base_url", "https://api.minimax.io/v1"),
        summary_style=summ.get(
            "style",
            "Summarize in 2-3 concise sentences capturing the key points.",
        ),
        hotkeys=Hotkeys(
            toggle_dictation=hk.get("toggle_dictation", "<cmd>+<alt>+d"),
            speak_selection=hk.get("speak_selection", "<cmd>+<alt>+s"),
            stop=hk.get("stop", "<cmd>+<alt>+."),
        ),
    )

import re

from echopad.config import Config

# Reasoning models (e.g. MiniMax M3) inline their chain-of-thought in the message
# content inside <think>...</think> before the actual answer. We must drop it so
# only the answer is spoken.
_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)


def strip_reasoning(text: str) -> str:
    """Remove inline <think>...</think> reasoning blocks, leaving the answer."""
    return _THINK_RE.sub("", text).strip()


def build_messages(text: str, summary_style: str) -> list[dict]:
    system = (
        "You summarize text that will be read aloud by a text-to-speech voice. "
        f"{summary_style} "
        "Output only the summary itself, with no preamble, labels, or markdown."
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": text},
    ]


def make_client(config: Config):
    from openai import OpenAI

    return OpenAI(
        api_key=config.minimax_api_key,
        base_url=config.summarizer_base_url,
    )


def summarize(text: str, config: Config, client=None) -> str:
    if not text.strip():
        raise ValueError("nothing to summarize")
    client = client or make_client(config)
    response = client.chat.completions.create(
        model=config.summarizer_model,
        messages=build_messages(text, config.summary_style),
        temperature=0.3,
    )
    return strip_reasoning(response.choices[0].message.content)

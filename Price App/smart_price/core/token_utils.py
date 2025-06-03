import logging
from pathlib import Path
from typing import List, Dict, Any

try:
    import tiktoken
except Exception:  # pragma: no cover - fallback when tiktoken missing
    class _SimpleTok:
        def encode(self, text: str) -> list[str]:
            return text.split()

    class _Stub:
        def encoding_for_model(self, _model: str) -> _SimpleTok:
            return _SimpleTok()

        def get_encoding(self, _name: str) -> _SimpleTok:
            return _SimpleTok()

    tiktoken = _Stub()  # type: ignore
from smart_price import config

logger = logging.getLogger("smart_price")


def num_tokens_from_text(text: str, model: str) -> int:
    """Return number of tokens in ``text`` for ``model``."""
    try:
        enc = tiktoken.encoding_for_model(model)
    except Exception:
        enc = tiktoken.get_encoding("cl100k_base")
    return len(enc.encode(text or ""))


def num_tokens_from_messages(messages: List[Dict[str, Any]], model: str) -> int:
    """Return number of tokens used by a list of chat ``messages``."""
    try:
        enc = tiktoken.encoding_for_model(model)
    except Exception:
        enc = tiktoken.get_encoding("cl100k_base")

    tokens_per_message = 3
    tokens_per_name = 1
    num_tokens = 0
    for message in messages:
        num_tokens += tokens_per_message
        for key, value in message.items():
            if value is None:
                continue
            num_tokens += len(enc.encode(str(value)))
            if key == "name":
                num_tokens += tokens_per_name
    num_tokens += 3
    return num_tokens


def log_token_counts(pdf_name: str, input_tokens: int, output_tokens: int) -> None:
    """Append token statistics for ``pdf_name`` to ``token_log.txt``."""
    log_file = Path(config.LOG_PATH).with_name("token_log.txt")
    line = f"{pdf_name}\tinput:{input_tokens}\toutput:{output_tokens}\ttotal:{input_tokens + output_tokens}\n"
    try:
        with open(log_file, "a", encoding="utf-8") as fh:
            fh.write(line)
    except Exception as exc:  # pragma: no cover - log errors
        logger.error("Token log write failed: %s", exc)
    logger.info(
        "Token usage for %s - input=%d, output=%d, total=%d",
        pdf_name,
        input_tokens,
        output_tokens,
        input_tokens + output_tokens,
    )
    print(
        f"{pdf_name} tokens -> input: {input_tokens}, output: {output_tokens}, total: {input_tokens + output_tokens}"
    )

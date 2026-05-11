"""Anthropic API client wrapper with streaming and retry."""

from collections.abc import Iterator
from typing import Any

import structlog
from anthropic import Anthropic
from tenacity import retry, stop_after_attempt, wait_exponential

from samantha.config import get_settings

logger = structlog.get_logger(__name__)

_client: Anthropic | None = None


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        settings = get_settings()
        _client = Anthropic(api_key=settings.anthropic_api_key or None)
    return _client


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True,
)
def chat(
    messages: list[dict[str, Any]],
    system_prompt: str,
    stream: bool = True,
) -> Iterator[str] | str:
    """Send messages to the model.

    When stream=True, returns an iterator yielding text chunks.
    When stream=False, returns the full response string.
    """
    settings = get_settings()
    client = _get_client()

    if stream:
        return _stream(client, messages, system_prompt, settings.model_id)
    else:
        return _complete(client, messages, system_prompt, settings.model_id)


def _stream(
    client: Anthropic,
    messages: list[dict[str, Any]],
    system_prompt: str,
    model_id: str,
) -> Iterator[str]:
    with client.messages.stream(
        model=model_id,
        max_tokens=2048,
        system=system_prompt,
        messages=messages,
    ) as stream:
        yield from stream.text_stream
        usage = stream.get_final_message().usage
    logger.info("tokens", input=usage.input_tokens, output=usage.output_tokens)


def _complete(
    client: Anthropic,
    messages: list[dict[str, Any]],
    system_prompt: str,
    model_id: str,
) -> str:
    response = client.messages.create(
        model=model_id,
        max_tokens=2048,
        system=system_prompt,
        messages=messages,
    )
    logger.info("tokens", input=response.usage.input_tokens, output=response.usage.output_tokens)
    return response.content[0].text  # type: ignore[union-attr]

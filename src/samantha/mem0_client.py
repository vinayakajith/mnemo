"""Mem0 configured for Anthropic LLM + local BGE embeddings + pgvector.

Fallback note: if the 'huggingface' embedder provider fails (e.g., missing
sentence-transformers), mem0 supports a custom embedder via the
`EmbeddingBase` extension point. See mem0.embeddings.base.EmbeddingBase.
"""

import contextlib
import io
from typing import Any

import structlog

from samantha.config import Settings

logger = structlog.get_logger(__name__)


def _get_mem0_config(settings: Settings) -> dict[str, Any]:
    return {
        "llm": {
            "provider": "anthropic",
            "config": {
                "model": settings.model_id,
                "api_key": settings.anthropic_api_key,
                # None → mem0's has_temperature check fails → param not sent.
                # Required because claude-opus-4-7+ rejects the temperature field.
                "temperature": None,
            },
        },
        "embedder": {
            # Uses sentence-transformers locally — no API key needed.
            "provider": "huggingface",
            "config": {"model": "BAAI/bge-large-en-v1.5"},
        },
        "vector_store": {
            "provider": "pgvector",
            "config": {
                "connection_string": settings.postgres_dsn,
                "embedding_model_dims": 1024,
                "collection_name": "samantha_semantic",
            },
        },
    }


def build_mem0(settings: Settings) -> Any:
    """Return a configured Mem0 Memory instance, or NoopMem0 on failure."""
    from mem0 import Memory

    _sink = io.StringIO()
    try:
        with contextlib.redirect_stdout(_sink), contextlib.redirect_stderr(_sink):
            mem = Memory.from_config(_get_mem0_config(settings))
        logger.info("mem0 initialized", embedder="huggingface/bge-large-en-v1.5")
        return mem
    except Exception as exc:
        logger.error(
            "mem0 init failed — semantic facts disabled; episodes still work",
            error=str(exc),
        )
        return _NoopMem0()


def get_all_facts(mem0: Any, user_id: str) -> list[dict[str, Any]]:
    """Return all semantic facts for a user."""
    try:
        result = mem0.get_all(filters={"user_id": user_id})
        if isinstance(result, dict):
            return result.get("results", [])
        return result or []
    except Exception as exc:
        logger.warning("mem0 get_all failed", error=str(exc))
        return []


def add_exchange(mem0: Any, user_id: str, user_text: str, assistant_text: str) -> None:
    """Hand an exchange to mem0 for semantic fact extraction."""
    messages = [
        {"role": "user", "content": user_text},
        {"role": "assistant", "content": assistant_text},
    ]
    try:
        _sink = io.StringIO()
        with contextlib.redirect_stdout(_sink), contextlib.redirect_stderr(_sink):
            mem0.add(messages, user_id=user_id)
    except Exception as exc:
        logger.warning("mem0 add failed", error=str(exc))


def search_facts(mem0: Any, user_id: str, query: str) -> list[dict[str, Any]]:
    """Search semantic facts by query similarity."""
    try:
        result = mem0.search(query, filters={"user_id": user_id}, top_k=10)
        if isinstance(result, dict):
            return result.get("results", [])
        return result or []
    except Exception as exc:
        logger.warning("mem0 search failed", error=str(exc))
        return []


def delete_fact(mem0: Any, memory_id: str) -> None:
    """Delete a single semantic fact by id."""
    try:
        mem0.delete(memory_id)
    except Exception as exc:
        logger.warning("mem0 delete failed", error=str(exc))


class _NoopMem0:
    """Returned when mem0 can't be initialized; silences all calls."""

    def add(self, *args: Any, **kwargs: Any) -> None:
        pass

    def get_all(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return {"results": []}

    def search(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return {"results": []}

    def delete(self, *args: Any, **kwargs: Any) -> None:
        pass

"""Local embedder using BAAI/bge-large-en-v1.5 (1024-dim).

Model downloads on first use (~1.3GB) and caches to ~/.cache/huggingface/.
"""

from functools import lru_cache

import numpy as np
import structlog

MODEL_NAME = "BAAI/bge-large-en-v1.5"
EMBEDDING_DIM = 1024

logger = structlog.get_logger(__name__)


@lru_cache(maxsize=1)
def _model():
    from sentence_transformers import SentenceTransformer

    logger.info("loading embedding model — may download ~1.3GB on first run", model=MODEL_NAME)
    m = SentenceTransformer(MODEL_NAME)
    logger.info("embedding model ready", model=MODEL_NAME)
    return m


def embed(text: str) -> np.ndarray:
    """Returns a normalized 1024-dim float32 vector."""
    return _model().encode(text, normalize_embeddings=True)


def embed_batch(texts: list[str]) -> np.ndarray:
    """Embed multiple texts; returns shape (len(texts), 1024)."""
    return _model().encode(texts, normalize_embeddings=True, batch_size=32)

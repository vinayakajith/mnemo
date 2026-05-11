"""Embedding tests — skipped by default (requires ~1.3GB model download).

Run with: ENABLE_EMBEDDING_TESTS=1 pytest tests/test_embeddings.py
"""

import os

import pytest

ENABLED = os.environ.get("ENABLE_EMBEDDING_TESTS", "0") == "1"
skip = pytest.mark.skipif(not ENABLED, reason="set ENABLE_EMBEDDING_TESTS=1 to run")


@skip
def test_embed_returns_correct_dim():
    from samantha.embeddings import EMBEDDING_DIM, embed

    vec = embed("hello world")
    assert vec.shape == (EMBEDDING_DIM,)
    assert EMBEDDING_DIM == 1024


@skip
def test_embed_is_normalized():
    import numpy as np

    from samantha.embeddings import embed

    vec = embed("normalization check")
    norm = float(np.linalg.norm(vec))
    assert abs(norm - 1.0) < 1e-5


@skip
def test_embed_batch_shape():
    from samantha.embeddings import embed_batch

    texts = ["first sentence", "second sentence", "third sentence"]
    vecs = embed_batch(texts)
    assert vecs.shape == (3, 1024)


@skip
def test_embed_different_texts_differ():
    import numpy as np

    from samantha.embeddings import embed

    a = embed("I bombed the interview today")
    b = embed("I shipped the project and it went great")
    similarity = float(np.dot(a, b))
    # Should be positive (same domain) but not identical
    assert similarity < 0.99
    assert similarity > 0.0


@skip
def test_embed_similar_texts_close():
    import numpy as np

    from samantha.embeddings import embed

    a = embed("went to the gym this morning")
    b = embed("exercised at the gym today")
    similarity = float(np.dot(a, b))
    assert similarity > 0.8

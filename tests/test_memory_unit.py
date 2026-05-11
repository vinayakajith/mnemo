"""MemorySession unit tests — skipped by default (requires running postgres).

Run with:
    docker compose up -d
    uv run python scripts/migrate.py
    ENABLE_DB_TESTS=1 pytest tests/test_memory_unit.py
"""

import os
import uuid

import pytest

ENABLED = os.environ.get("ENABLE_DB_TESTS", "0") == "1"
skip = pytest.mark.skipif(not ENABLED, reason="set ENABLE_DB_TESTS=1 with postgres running")

TEST_DSN = "postgresql://samantha:samantha_dev@localhost:5432/samantha"


def _test_settings():
    """Minimal Settings-like object pointing at test DB."""

    class _S:
        postgres_dsn = TEST_DSN
        anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY", "test-key")
        model_id = "claude-opus-4-7"
        default_user_id = f"test-{uuid.uuid4().hex[:8]}"

    return _S()


@skip
def test_new_user_is_new():
    from samantha.memory import MemorySession

    s = _test_settings()
    mem = MemorySession(user_id=s.default_user_id, settings=s)
    try:
        assert mem.is_new_user() is True
    finally:
        mem.close()


@skip
def test_mark_onboarded():
    from samantha.memory import MemorySession

    s = _test_settings()
    mem = MemorySession(user_id=s.default_user_id, settings=s)
    try:
        assert mem.is_new_user() is True
        mem.mark_onboarded()
        assert mem.is_new_user() is False
    finally:
        mem.close()


@skip
def test_start_end_conversation():
    from samantha.memory import MemorySession

    s = _test_settings()
    mem = MemorySession(user_id=s.default_user_id, settings=s)
    try:
        conv_id = mem.start_conversation(kind="chat")
        assert isinstance(conv_id, int)
        assert conv_id > 0
        mem.end_conversation(conv_id, "/tmp/test.json", [])
    finally:
        mem.close()


@skip
def test_noop_memory_full_interface():
    """NoopMemory implements the full interface without errors."""
    from samantha.memory import NoopMemory

    mem = NoopMemory()
    assert mem.get_context("anything") == ""
    mem.write("u", "a")
    assert mem.is_new_user() is False
    mem.mark_onboarded()
    assert mem.start_conversation() == 0
    mem.end_conversation(0, "", [])
    assert mem.get_all_facts() == []
    mem.delete_fact("any-id")
    assert mem.search_facts("query") == []
    mem.close()


@skip
def test_get_context_returns_string():
    from samantha.memory import MemorySession

    s = _test_settings()
    mem = MemorySession(user_id=s.default_user_id, settings=s)
    try:
        ctx = mem.get_context("how's it going")
        # At minimum should have datetime block
        assert isinstance(ctx, str)
        assert "current_datetime" in ctx
    finally:
        mem.close()


@skip
def test_episode_count_increments_after_consolidation():
    import json

    from samantha.memory import MemorySession

    s = _test_settings()
    mem = MemorySession(user_id=s.default_user_id, settings=s)
    try:
        before = mem.episode_count()

        fake_transcript = [
            {"role": "user", "content": "I shipped a major feature today after weeks of work."},
            {"role": "assistant", "content": "that's earned. sit with it."},
        ]

        def _fake_llm(messages, system_prompt, stream=False):
            return json.dumps([{"summary": "Shipped a major feature.", "importance": 0.8}])

        import samantha.consolidation as cons

        original = cons.extract_episodes
        cons.extract_episodes = lambda h, fn: original(h, _fake_llm)  # type: ignore[assignment]
        try:
            mem.consolidate(0, fake_transcript)
        finally:
            cons.extract_episodes = original  # type: ignore[assignment]

        assert mem.episode_count() == before + 1
    finally:
        mem.close()

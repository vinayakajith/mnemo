"""Unit tests for episode extraction — mocked LLM, no external services."""

import json

from samantha.consolidation import extract_episodes


def _make_llm(response: str):
    """Returns a fake llm.chat callable that echoes a fixed string."""

    def fake_chat(messages, system_prompt, stream=False):
        assert stream is False, "consolidation must use stream=False"
        return response

    return fake_chat


SAMPLE_HISTORY = [
    {"role": "user", "content": "I finally finished the side project I've been putting off."},
    {"role": "assistant", "content": "hell yes. how long has that been sitting?"},
    {"role": "user", "content": "like three months. feels good."},
    {"role": "assistant", "content": "sit with it. you do that thing where you skip the win."},
]


def test_extract_valid_episodes():
    payload = json.dumps(
        [
            {"summary": "Finished a side project after three months.", "importance": 0.7},
            {"summary": "Reflected on tendency to skip celebrating wins.", "importance": 0.5},
        ]
    )
    episodes = extract_episodes(SAMPLE_HISTORY, _make_llm(payload))
    assert len(episodes) == 2
    assert episodes[0]["summary"] == "Finished a side project after three months."
    assert abs(episodes[0]["importance"] - 0.7) < 1e-6


def test_extract_strips_markdown_fences():
    payload = '```json\n[{"summary": "shipped something", "importance": 0.6}]\n```'
    episodes = extract_episodes(SAMPLE_HISTORY, _make_llm(payload))
    assert len(episodes) == 1
    assert "shipped" in episodes[0]["summary"]


def test_extract_empty_history():
    episodes = extract_episodes([], _make_llm("[]"))
    assert episodes == []


def test_extract_malformed_json_returns_empty():
    episodes = extract_episodes(SAMPLE_HISTORY, _make_llm("not json at all"))
    assert episodes == []


def test_extract_skips_invalid_entries():
    payload = json.dumps(
        [
            {"summary": "good entry", "importance": 0.5},
            {"not_summary": "bad entry"},  # missing keys
            {"summary": "another good one", "importance": 0.8},
        ]
    )
    episodes = extract_episodes(SAMPLE_HISTORY, _make_llm(payload))
    assert len(episodes) == 2


def test_extract_clamps_importance_to_float():
    payload = json.dumps([{"summary": "something happened", "importance": "0.9"}])
    episodes = extract_episodes(SAMPLE_HISTORY, _make_llm(payload))
    assert len(episodes) == 1
    assert isinstance(episodes[0]["importance"], float)


def test_llm_exception_returns_empty():
    def bad_llm(messages, system_prompt, stream=False):
        raise RuntimeError("api down")

    episodes = extract_episodes(SAMPLE_HISTORY, bad_llm)
    assert episodes == []

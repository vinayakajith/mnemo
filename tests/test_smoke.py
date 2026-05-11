"""Smoke tests — imports, config, prompt loading, memory stub."""

from pathlib import Path


def test_imports() -> None:
    import samantha  # noqa: F401
    from samantha import (  # noqa: F401
        chat,
        cli,
        cold_start,
        config,
        consolidation,
        embeddings,
        llm,
        mem0_client,
        memory,
        prompts,
    )


def test_config_loads(monkeypatch: object, tmp_path: Path) -> None:
    from samantha.config import Settings

    env_file = tmp_path / ".env"
    env_file.write_text("ANTHROPIC_API_KEY=test-key\nMODEL_ID=claude-opus-4-7\n")

    settings = Settings(_env_file=str(env_file))  # type: ignore[call-arg]
    assert settings.anthropic_api_key == "test-key"
    assert settings.model_id == "claude-opus-4-7"


def test_load_system_prompt(tmp_path: Path) -> None:
    from samantha.prompts import load_system_prompt

    prompt_file = tmp_path / "test_prompt.txt"
    prompt_file.write_text("  You are Samantha.  \n")

    result = load_system_prompt(str(prompt_file))
    assert result == "You are Samantha."


def test_load_system_prompt_missing(tmp_path: Path) -> None:
    import pytest

    from samantha.prompts import load_system_prompt

    with pytest.raises(FileNotFoundError):
        load_system_prompt(str(tmp_path / "nonexistent.txt"))


def test_load_system_prompt_empty(tmp_path: Path) -> None:
    import pytest

    from samantha.prompts import load_system_prompt

    empty_file = tmp_path / "empty.txt"
    empty_file.write_text("   \n  ")

    with pytest.raises(ValueError):
        load_system_prompt(str(empty_file))


def test_noop_memory() -> None:
    from samantha.memory import NoopMemory

    mem = NoopMemory()
    assert mem.get_context("anything") == ""
    mem.write("user input", "assistant output")
    assert mem.is_new_user() is False
    assert mem.start_conversation() == 0
    assert mem.get_all_facts() == []
    mem.close()  # should not raise


def test_score_episode_import() -> None:
    from samantha.memory import score_episode

    s = score_episode(1.0, 0.0, 1.0)
    assert 0.0 <= s <= 1.01  # small float tolerance


def test_config_has_new_fields() -> None:
    from samantha.config import Settings

    s = Settings(
        _env_file=None,  # type: ignore[call-arg]
        anthropic_api_key="k",
        model_id="claude-opus-4-7",
    )
    assert hasattr(s, "postgres_dsn")
    assert hasattr(s, "default_user_id")

"""Smoke tests — imports, config, prompt loading, memory stub."""

from pathlib import Path


def test_imports() -> None:
    import samantha  # noqa: F401
    from samantha import chat, cli, config, llm, memory, prompts  # noqa: F401


def test_config_loads(monkeypatch: object, tmp_path: Path) -> None:
    from samantha.config import Settings

    env_file = tmp_path / ".env"
    env_file.write_text("AWS_REGION=us-west-2\nBEDROCK_MODEL_ID=test-model\n")

    settings = Settings(_env_file=str(env_file))  # type: ignore[call-arg]
    assert settings.aws_region == "us-west-2"
    assert settings.bedrock_model_id == "test-model"


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
    mem.write("user input", "assistant output")  # should not raise

"""System prompt loader."""

from pathlib import Path


def load_system_prompt(path: str) -> str:
    """Read system prompt from file. Fails loudly if missing or empty."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"System prompt not found: {path}")
    text = p.read_text(encoding="utf-8").strip()
    if not text:
        raise ValueError(f"System prompt is empty: {path}")
    return text

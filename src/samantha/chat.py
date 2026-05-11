"""ChatSession — UI-agnostic conversation management."""

import json
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from samantha import llm
from samantha.memory import NoopMemory


class ChatSession:
    def __init__(
        self,
        system_prompt: str,
        model_id: str,
        memory: NoopMemory | None = None,
    ) -> None:
        self.system_prompt = system_prompt
        self.model_id = model_id
        self.memory: NoopMemory = memory or NoopMemory()
        self.history: list[dict[str, Any]] = []
        self._input_tokens: int = 0
        self._output_tokens: int = 0

    def add_user(self, text: str) -> None:
        self.history.append({"role": "user", "content": text})

    def add_assistant(self, text: str) -> None:
        self.history.append({"role": "assistant", "content": text})

    def send(self, user_text: str) -> Iterator[str]:
        """Add user turn, stream assistant reply, update history."""
        mem_context = self.memory.get_context(user_text)
        effective_text = f"{mem_context}\n\n{user_text}".strip() if mem_context else user_text

        self.add_user(effective_text)

        chunks: list[str] = []
        for chunk in llm.chat(self.history, self.system_prompt, stream=True):  # type: ignore[union-attr]
            chunks.append(chunk)
            yield chunk

        assistant_text = "".join(chunks)
        self.add_assistant(assistant_text)
        self.memory.write(user_text, assistant_text)

    def token_usage(self) -> dict[str, int]:
        return {"input": self._input_tokens, "output": self._output_tokens}

    def save_transcript(self, path: str | Path) -> None:
        """Write JSON transcript with timestamp, model, and full history."""
        out = {
            "timestamp": datetime.now(tz=UTC).isoformat(),
            "model_id": self.model_id,
            "history": self.history,
        }
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")

    def clear(self) -> None:
        self.history.clear()

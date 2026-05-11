"""ChatSession — UI-agnostic conversation management."""

import json
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from samantha import llm
from samantha.memory import NoopMemory


def _transcript_path(transcripts_dir: str) -> Path:
    ts = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
    return Path(transcripts_dir) / f"session_{ts}.json"


class ChatSession:
    def __init__(
        self,
        system_prompt: str,
        model_id: str,
        memory: Any = None,  # NoopMemory | MemorySession
    ) -> None:
        self.system_prompt = system_prompt
        self.model_id: str = model_id
        self.memory = memory if memory is not None else NoopMemory()
        self.history: list[dict[str, Any]] = []
        self._input_tokens: int = 0
        self._output_tokens: int = 0
        self._conversation_id: int = 0

    def start_session(self) -> None:
        """Register this conversation in the DB (no-op for NoopMemory)."""
        self._conversation_id = self.memory.start_conversation()

    def end_session(self, transcripts_dir: str = "transcripts") -> Path:
        """Save transcript and trigger post-session consolidation."""
        path = _transcript_path(transcripts_dir)
        self.save_transcript(path)
        self.memory.end_conversation(self._conversation_id, str(path), self.history)
        return path

    def add_user(self, text: str) -> None:
        self.history.append({"role": "user", "content": text})

    def add_assistant(self, text: str) -> None:
        self.history.append({"role": "assistant", "content": text})

    def send(self, user_text: str) -> Iterator[str]:
        """Add user turn, stream assistant reply, update history.

        Memory context is injected into the system prompt each turn — the
        history stays clean with actual user messages only.
        """
        mem_context = self.memory.get_context(user_text)
        effective_system = (
            f"{self.system_prompt}\n\n{mem_context}" if mem_context else self.system_prompt
        )

        self.add_user(user_text)

        chunks: list[str] = []
        for chunk in llm.chat(self.history, effective_system, stream=True):  # type: ignore[union-attr]
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

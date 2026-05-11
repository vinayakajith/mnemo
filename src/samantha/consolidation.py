"""Episode extraction from conversation transcripts."""

import json
import re
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

CONSOLIDATION_PROMPT = """\
Read this conversation transcript and return a JSON array of notable
episodes — events, facts, or shifts worth remembering for future
conversations.

For each episode return:
{{
  "summary": "one-sentence description in third person past tense",
  "importance": float 0-1
    (0.3 = casual mention, 0.6 = significant, 0.9 = major life event)
}}

Skip small talk, pleasantries, and meta-discussion. Only return things
that would matter to remember weeks from now.

Return ONLY the JSON array. No prose, no markdown fences.

Transcript:
{transcript}
"""


def _format_transcript(history: list[dict[str, Any]]) -> str:
    lines = []
    for turn in history:
        role = turn.get("role", "unknown").upper()
        content = turn.get("content", "")
        lines.append(f"{role}: {content}")
    return "\n\n".join(lines)


def _parse_json(text: str) -> list[dict[str, Any]]:
    text = text.strip()
    # Strip markdown code fences if present
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


def extract_episodes(history: list[dict[str, Any]], llm_complete_fn: Any) -> list[dict[str, Any]]:
    """Call LLM to extract notable episodes from a conversation transcript.

    Args:
        history: ChatSession.history (list of role/content dicts)
        llm_complete_fn: callable(messages, system_prompt) -> str

    Returns:
        List of {"summary": str, "importance": float} dicts.
    """
    if not history:
        return []

    transcript = _format_transcript(history)
    prompt = CONSOLIDATION_PROMPT.format(transcript=transcript)

    try:
        raw = llm_complete_fn(
            messages=[{"role": "user", "content": prompt}],
            system_prompt="You are a concise memory extraction assistant. Return only valid JSON.",
            stream=False,
        )
        episodes = _parse_json(raw)
        # Validate shape
        valid = []
        for ep in episodes:
            if isinstance(ep, dict) and "summary" in ep and "importance" in ep:
                valid.append(
                    {
                        "summary": str(ep["summary"]),
                        "importance": float(ep["importance"]),
                    }
                )
        logger.info("episodes extracted", count=len(valid))
        return valid
    except Exception as exc:
        logger.error("episode extraction failed", error=str(exc))
        return []

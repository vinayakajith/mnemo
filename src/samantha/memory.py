"""Memory layer: NoopMemory (tests) + MemorySession (real, Phase 2+)."""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# Scoring
# ──────────────────────────────────────────────────────────────────────────────


def score_episode(similarity: float, days_since: float, importance: float) -> float:
    """Friend-philosophy retrieval score (0-1, threshold 0.4)."""
    recency_decay = math.exp(-days_since / 30)
    return 0.5 * similarity + 0.3 * recency_decay + 0.2 * importance


# ──────────────────────────────────────────────────────────────────────────────
# Noop stub (used by tests + as fallback when DB is unavailable)
# ──────────────────────────────────────────────────────────────────────────────


class NoopMemory:
    """Phase 2 replaced this with MemorySession. Kept for tests and fallback."""

    def get_context(self, user_input: str) -> str:
        return ""

    def write(self, user_input: str, assistant_output: str) -> None:
        pass

    def is_new_user(self) -> bool:
        return False

    def mark_onboarded(self) -> None:
        pass

    def start_conversation(self, kind: str = "chat") -> int:
        return 0

    def end_conversation(
        self, conversation_id: int, transcript_path: str, transcript: list[dict[str, Any]]
    ) -> None:
        pass

    def get_all_facts(self) -> list[dict[str, Any]]:
        return []

    def delete_fact(self, memory_id: str) -> None:
        pass

    def search_facts(self, query: str) -> list[dict[str, Any]]:
        return []

    def close(self) -> None:
        pass


# ──────────────────────────────────────────────────────────────────────────────
# Real implementation
# ──────────────────────────────────────────────────────────────────────────────


def _make_pool(dsn: str):
    from pgvector.psycopg import register_vector
    from psycopg.rows import dict_row
    from psycopg_pool import ConnectionPool

    return ConnectionPool(
        conninfo=dsn,
        min_size=1,
        max_size=5,
        open=True,
        configure=lambda conn: (register_vector(conn), conn.cursor_factory.__class__),
        kwargs={"row_factory": dict_row},
    )


def _relative_time(dt: datetime) -> str:
    days = (datetime.now(tz=UTC) - dt).days
    if days == 0:
        return "today"
    if days == 1:
        return "yesterday"
    if days < 7:
        return f"{days} days ago"
    if days < 14:
        return "last week"
    weeks = days // 7
    if weeks < 5:
        return f"{weeks} weeks ago"
    return f"~{days // 30} months ago"


class MemorySession:
    """Real memory: Mem0 for semantic facts, pgvector episodes table for events."""

    def __init__(self, user_id: str, settings: Any) -> None:
        from samantha.mem0_client import build_mem0

        self.user_id = user_id
        self.settings = settings
        self._pool = _make_pool(settings.postgres_dsn)
        self.mem0 = build_mem0(settings)
        self._ensure_user_exists()

    # ── internal ──────────────────────────────────────────────────────────────

    def _ensure_user_exists(self) -> None:
        with self._pool.connection() as conn:
            conn.execute(
                "INSERT INTO users (id) VALUES (%s) ON CONFLICT (id) DO NOTHING",
                (self.user_id,),
            )

    # ── identity ──────────────────────────────────────────────────────────────

    def is_new_user(self) -> bool:
        """True when this user has never completed onboarding."""
        with self._pool.connection() as conn:
            row = conn.execute(
                "SELECT onboarded_at FROM users WHERE id = %s", (self.user_id,)
            ).fetchone()
            return row is None or row["onboarded_at"] is None

    def mark_onboarded(self) -> None:
        with self._pool.connection() as conn:
            conn.execute("UPDATE users SET onboarded_at = NOW() WHERE id = %s", (self.user_id,))

    # ── conversation lifecycle ─────────────────────────────────────────────────

    def start_conversation(self, kind: str = "chat") -> int:
        with self._pool.connection() as conn:
            row = conn.execute(
                "INSERT INTO conversations (user_id, kind) VALUES (%s, %s) RETURNING id",
                (self.user_id, kind),
            ).fetchone()
            return row["id"]

    def end_conversation(
        self, conversation_id: int, transcript_path: str, transcript: list[dict[str, Any]]
    ) -> None:
        with self._pool.connection() as conn:
            conn.execute(
                "UPDATE conversations SET ended_at = NOW(), transcript_path = %s WHERE id = %s",
                (transcript_path, conversation_id),
            )
        self.consolidate(conversation_id, transcript)

    # ── context retrieval (called before every LLM turn) ──────────────────────

    def get_context(self, user_input: str) -> str:
        parts: list[str] = []

        # Datetime block — always present
        now = datetime.now(tz=UTC)
        parts.append(f"<current_datetime>{now.isoformat()}</current_datetime>")

        # Semantic facts from Mem0 — always loaded (usually small)
        facts = self.get_all_facts()
        if facts:
            bullets = "\n".join(f"- {f['memory']}" for f in facts if "memory" in f)
            if bullets:
                parts.append(f"<user_facts>\n{bullets}\n</user_facts>")

        # Recent episodes (last 7 days, up to 5)
        recent = self._recent_episodes(days=7, limit=5)
        if recent:
            bullets = "\n".join(
                f"- {_relative_time(ep['occurred_at'])}: {ep['summary']}" for ep in recent
            )
            parts.append(f"<recent_episodes>\n{bullets}\n</recent_episodes>")

        # Relevant episodes via vector search + scoring
        relevant = self._relevant_episodes(user_input, exclude_ids={ep["id"] for ep in recent})
        if relevant:
            bullets = "\n".join(
                f"- {_relative_time(ep['occurred_at'])}: {ep['summary']}" for ep in relevant
            )
            parts.append(f"<relevant_episodes>\n{bullets}\n</relevant_episodes>")

        return "\n\n".join(parts) if parts else ""

    def _recent_episodes(self, days: int, limit: int) -> list[dict[str, Any]]:
        cutoff = datetime.now(tz=UTC) - timedelta(days=days)
        try:
            with self._pool.connection() as conn:
                rows = conn.execute(
                    """
                    SELECT id, summary, occurred_at
                    FROM episodes
                    WHERE user_id = %s AND occurred_at >= %s
                    ORDER BY occurred_at DESC
                    LIMIT %s
                    """,
                    (self.user_id, cutoff, limit),
                ).fetchall()
            return list(rows)
        except Exception as exc:
            logger.warning("recent episodes query failed", error=str(exc))
            return []

    def _relevant_episodes(
        self, query: str, exclude_ids: set[int], limit: int = 5
    ) -> list[dict[str, Any]]:
        from samantha.embeddings import embed

        try:
            query_vec = embed(query)
            with self._pool.connection() as conn:
                rows = conn.execute(
                    """
                    SELECT id, summary, importance, occurred_at,
                           1 - (embedding <=> %s::vector) AS similarity
                    FROM episodes
                    WHERE user_id = %s
                    ORDER BY embedding <=> %s::vector
                    LIMIT 20
                    """,
                    (query_vec.tolist(), self.user_id, query_vec.tolist()),
                ).fetchall()

            now = datetime.now(tz=UTC)
            scored = []
            for row in rows:
                if row["id"] in exclude_ids:
                    continue
                days_since = (now - row["occurred_at"]).days
                s = score_episode(row["similarity"], days_since, row["importance"])
                if s >= 0.4:
                    scored.append((s, dict(row)))

            scored.sort(key=lambda x: x[0], reverse=True)
            return [ep for _, ep in scored[:limit]]
        except Exception as exc:
            logger.warning("relevant episodes query failed", error=str(exc))
            return []

    # ── write ─────────────────────────────────────────────────────────────────

    def write(self, user_input: str, assistant_output: str) -> None:
        """Pass exchange to Mem0 for semantic fact extraction (async-friendly; does not block)."""
        from samantha.mem0_client import add_exchange

        add_exchange(self.mem0, self.user_id, user_input, assistant_output)

    # ── consolidation (called at session end) ──────────────────────────────────

    def consolidate(self, conversation_id: int, transcript: list[dict[str, Any]]) -> None:
        """Extract notable episodes from transcript; embed and store them."""
        from samantha import llm
        from samantha.consolidation import extract_episodes
        from samantha.embeddings import embed

        episodes = extract_episodes(transcript, llm.chat)
        if not episodes:
            return

        now = datetime.now(tz=UTC)
        try:
            with self._pool.connection() as conn:
                for ep in episodes:
                    vec = embed(ep["summary"])
                    conn.execute(
                        """
                        INSERT INTO episodes
                            (user_id, summary, embedding, importance, occurred_at, conversation_id)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        """,
                        (
                            self.user_id,
                            ep["summary"],
                            vec.tolist(),
                            ep["importance"],
                            now,
                            conversation_id,
                        ),
                    )
            logger.info("episodes stored", count=len(episodes))
        except Exception as exc:
            logger.error("episode storage failed", error=str(exc))

    # ── fact management (for /memory and /forget) ──────────────────────────────

    def get_all_facts(self) -> list[dict[str, Any]]:
        from samantha.mem0_client import get_all_facts

        return get_all_facts(self.mem0, self.user_id)

    def search_facts(self, query: str) -> list[dict[str, Any]]:
        from samantha.mem0_client import search_facts

        return search_facts(self.mem0, self.user_id, query)

    def delete_fact(self, memory_id: str) -> None:
        from samantha.mem0_client import delete_fact

        delete_fact(self.mem0, memory_id)

    def episode_count(self) -> int:
        try:
            with self._pool.connection() as conn:
                row = conn.execute(
                    "SELECT COUNT(*) AS n FROM episodes WHERE user_id = %s", (self.user_id,)
                ).fetchone()
                return row["n"] if row else 0
        except Exception:
            return 0

    def close(self) -> None:
        try:
            self._pool.close()
        except Exception:
            pass

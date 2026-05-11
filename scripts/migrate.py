"""Idempotent schema migration + embedding model pre-warm.

Run once before first launch:
    uv run python scripts/migrate.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import psycopg
import structlog

from samantha.config import get_settings

logger = structlog.get_logger(__name__)

DDL = """\
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    onboarded_at TIMESTAMPTZ NULL
);

CREATE TABLE IF NOT EXISTS conversations (
    id BIGSERIAL PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ended_at TIMESTAMPTZ NULL,
    transcript_path TEXT NULL,
    kind TEXT NOT NULL DEFAULT 'chat'
);

CREATE TABLE IF NOT EXISTS episodes (
    id BIGSERIAL PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    summary TEXT NOT NULL,
    embedding VECTOR(1024),
    importance REAL NOT NULL DEFAULT 0.5,
    occurred_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_surfaced_at TIMESTAMPTZ NULL,
    conversation_id BIGINT NULL
);

CREATE INDEX IF NOT EXISTS idx_episodes_user_time
    ON episodes(user_id, occurred_at DESC);

CREATE INDEX IF NOT EXISTS idx_episodes_embedding
    ON episodes USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);
"""


def run_migrations(dsn: str) -> None:
    logger.info("connecting to postgres", dsn=dsn.split("@")[-1])
    with psycopg.connect(dsn, autocommit=True) as conn:
        logger.info("applying schema...")
        conn.execute(DDL)
        logger.info("schema applied (idempotent)")


def prewarm_embeddings() -> None:
    logger.info("pre-warming embedding model (may download ~1.3GB on first run)...")
    from samantha.embeddings import embed

    vec = embed("warmup")
    assert vec.shape == (1024,), f"unexpected embedding dim: {vec.shape}"
    logger.info("embedding model ready", dim=vec.shape[0])


def main() -> None:
    settings = get_settings()
    try:
        run_migrations(settings.postgres_dsn)
    except Exception as exc:
        print(f"ERROR: migration failed — is postgres running?\n  {exc}", file=sys.stderr)
        sys.exit(1)

    prewarm_embeddings()
    print("\n✓ migrate complete — ready to run `uv run samantha`")


if __name__ == "__main__":
    main()

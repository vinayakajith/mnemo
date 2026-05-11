# Samantha

A long-term personal AI presence — sharp older-sibling energy, brutally honest, has its own opinions, calls you on your shit, won't let you self-deceive. Not a chatbot. A presence with continuity and a stake in your growth. See `docs/manifesto.md` for the full design rationale.

## Quickstart

```bash
uv sync
cp .env.example .env
# fill in ANTHROPIC_API_KEY

# Start postgres
docker compose up -d

# Apply schema + pre-warm embedding model (~1.3GB download on first run)
uv run python scripts/migrate.py

# Chat
uv run samantha
```

First launch triggers a 10-20 turn onboarding conversation. After that, she drops directly into normal chat and references what she learned.

## CLI Commands

| Command | Action |
|---------|--------|
| `/quit` or `/exit` | Save transcript, consolidate memory, exit |
| `/save` | Save transcript now |
| `/clear` | Clear in-session history (keeps system prompt) |
| `/tokens` | Show token usage |
| `/memory` | Show known facts + episode count |
| `/forget <text>` | Find and delete a matching semantic fact |
| `/help` | List commands |

Ctrl+C saves transcript and exits cleanly.

Transcripts are written to `transcripts/` as JSON (gitignored).

## Running tests

```bash
# Unit + scoring tests (no external deps)
uv run pytest

# With DB integration tests (requires docker compose up -d + migrate.py)
ENABLE_DB_TESTS=1 uv run pytest

# With embedding tests (requires model to be cached from migrate.py)
ENABLE_EMBEDDING_TESTS=1 uv run pytest
```

## Run voice calibration scenarios

```bash
uv run python scripts/run_scenarios.py
```

Runs 10 scenarios in sequence; writes a transcript to `transcripts/scenarios_<ts>.json` for voice review.

## Resetting memory

```bash
docker compose down -v   # wipes postgres data (episodes, facts, onboarding)
docker compose up -d
uv run python scripts/migrate.py
```

## What's NOT here (yet)

- **Calendar / MCP** (Phase 3)
- **Telegram bot** (Phase 4)
- **Proactive messaging / background scheduler** (Phase 4)

## Project layout

```
src/samantha/
  config.py        — pydantic-settings, loads .env
  llm.py           — Anthropic client wrapper, streaming, retry
  prompts.py       — loads system prompt from file
  embeddings.py    — BAAI/bge-large-en-v1.5 local embedder (1024-dim)
  mem0_client.py   — Mem0 configured for Anthropic + BGE + pgvector
  consolidation.py — post-session episode extraction via LLM
  memory.py        — NoopMemory (tests) + MemorySession (real)
  cold_start.py    — first-launch onboarding flow
  chat.py          — ChatSession (UI-agnostic)
  cli.py           — Rich CLI entry point

prompts/
  samantha_v1.txt          — active system prompt
  onboarding_addendum.txt  — injected on first launch only

scripts/
  migrate.py        — idempotent schema + model pre-warm (run once)
  run_scenarios.py  — 10-turn voice calibration

docs/
  manifesto.md      — design rationale
  system_prompt.md  — system prompt source + iteration notes
```

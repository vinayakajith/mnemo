# mnemo

**A long-term personal AI companion with persistent memory, personality, and a philosophy.**

Not another chatbot wrapper. mnemo is a full-stack AI system built to feel like a real presence — sharp, honest, opinionated — with episodic memory that persists across every conversation and retrieval logic grounded in how human memory actually works.

---

## What makes this different

Most LLM apps are stateless. Every conversation starts from zero. mnemo keeps a structured memory of who you are — not by naively storing chat logs, but by extracting semantic facts and notable episodes, embedding them, and retrieving the *right* ones at the right time via a scored similarity search.

The goal: six months in, it should feel like talking to someone who knows you.

---

## Technical highlights

### Memory architecture
- **Semantic memory** — [Mem0](https://github.com/mem0ai/mem0) extracts structured facts from conversations using an LLM extraction pass (name, goals, relationships, recurring patterns)
- **Episodic memory** — a custom pgvector table stores notable events extracted post-session, embedded with `BAAI/bge-large-en-v1.5` (1024-dim)
- **Friend-philosophy retrieval scoring** — episodes are ranked by a composite score before injection:

```python
score = 0.5 * cosine_similarity      # semantic match to current query
      + 0.3 * exp(-days_since / 30)  # recency decay (half-life ~30 days)
      + 0.2 * importance             # LLM-assigned salience at extraction time
# threshold: 0.4 — below this, stay silent rather than surface weak matches
```

### Stack
| Layer | Technology |
|---|---|
| LLM | Claude claude-opus-4-7 (Anthropic API, streaming) |
| Embeddings | `BAAI/bge-large-en-v1.5` via sentence-transformers (local, 1024-dim) |
| Vector store | PostgreSQL + pgvector (ivfflat cosine index) |
| Semantic facts | Mem0 OSS (Anthropic LLM + HuggingFace embedder + pgvector) |
| DB client | psycopg3 + psycopg-pool (connection pooling) |
| Config | pydantic-settings (typed, validated, .env-backed) |
| CLI | Rich (streaming output, styled, slash commands) |
| Retry/backoff | tenacity |
| Tests | pytest (unit + integration, 34 tests) |
| Infra | Docker Compose (pgvector/pgvector:pg16) |

### Context injection (per-turn)
Every LLM call receives a fresh context block appended to the system prompt — not the user message — so conversation history stays clean:

```
<current_datetime>2026-05-11T15:30:00+00:00</current_datetime>

<user_facts>
- works as a software engineer at a startup
- currently reading "The Design of Everyday Things"
</user_facts>

<recent_episodes>
- yesterday: shipped a feature after two weeks of debugging
- 3 days ago: skipped the gym for the fourth day in a row
</recent_episodes>

<relevant_episodes>
- 3 weeks ago: had a difficult conversation with their manager about promotion timeline
</relevant_episodes>
```

### Post-session consolidation
At conversation end, an LLM pass extracts notable episodes from the full transcript and writes them to pgvector — available for retrieval in future sessions.

### Cold-start onboarding
First launch triggers a structured-but-natural interview — Samantha drives a 10-20 turn conversation to learn who you are. The system watches for a sentinel marker (`[ONBOARDING_COMPLETE]`) in the assistant output; on detection it strips the marker, consolidates the transcript, marks the user onboarded, and drops into normal chat. No forms. No setup wizard.

---

## Architecture

```
uv run samantha
        │
        ▼
    cli.py          ← Rich CLI, slash commands, signal handling
        │
        ▼
  ChatSession       ← UI-agnostic, history management, start/end session
        │
   ┌────┴──────────────────────────────────────┐
   │                                           │
   ▼                                           ▼
llm.py                                    memory.py
(Anthropic API,                       (MemorySession)
 streaming, retry)                         │
                                    ┌──────┴──────────┐
                                    │                 │
                                    ▼                 ▼
                               mem0_client        pgvector
                               (semantic          (episodic
                                facts)             events)
                                    │                 │
                                    └────────┬────────┘
                                             ▼
                                       consolidation.py
                                   (LLM episode extraction,
                                    post-session, async)
```

---

## Setup

```bash
# 1. Install dependencies
uv sync

# 2. Configure
cp .env.example .env
# → add ANTHROPIC_API_KEY

# 3. Start postgres
docker compose up -d

# 4. Apply schema + pre-warm embedding model (~1.3GB, one-time)
uv run python scripts/migrate.py

# 5. Chat
uv run samantha
```

## CLI commands

```
/memory          — show all known facts + episode count
/forget <text>   — search and delete a semantic fact
/save            — save transcript mid-session
/clear           — clear in-session history
/tokens          — token usage so far
/quit            — save, consolidate memory, exit
```

## Tests

```bash
uv run pytest                            # unit tests (no external deps)
ENABLE_DB_TESTS=1 uv run pytest          # + DB integration (needs docker)
ENABLE_EMBEDDING_TESTS=1 uv run pytest   # + embedding tests (needs model)
```

34 tests across: retrieval scoring (pure math), consolidation (mocked LLM), embedding (1024-dim normalization checks), memory session (DB lifecycle), imports and config.

---

## Design philosophy

The system is built around a specific theory of what a good AI influence looks like — not engagement-maximizing, not sycophantic, not a mirror. The companion has explicit biases:

- toward growth, not comfort
- toward truth, not agreement
- toward the long game, not short-term dopamine
- toward the user building real-world capability, not depending on it

This is encoded in the system prompt, reinforced by the retrieval design (silence below threshold = better than weak matches), and reflected in the onboarding flow.

Full design rationale: [`docs/manifesto.md`](docs/manifesto.md)

---

## Roadmap

| Phase | Status | Description |
|---|---|---|
| 1 — CLI harness | ✅ shipped | Personality + streaming CLI |
| 2 — Memory | ✅ shipped | Mem0 + pgvector + BGE embeddings |
| 3 — Situated awareness | planned | Calendar MCP, timezone, daily rhythms |
| 4 — Proactive presence | planned | Telegram bot, cron-driven check-ins |

---

## Project layout

```
src/samantha/
  config.py          pydantic-settings, typed config
  llm.py             Anthropic client, streaming, tenacity retry
  embeddings.py      BAAI/bge-large-en-v1.5, lazy-loaded, normalized
  mem0_client.py     Mem0 with Anthropic LLM + pgvector
  consolidation.py   Post-session episode extraction
  memory.py          NoopMemory (tests) + MemorySession (real)
  cold_start.py      First-launch onboarding flow
  chat.py            ChatSession (UI-agnostic)
  cli.py             Rich CLI entry point

prompts/
  samantha_v1.txt          Active system prompt
  onboarding_addendum.txt  Injected on first launch

scripts/
  migrate.py         Idempotent schema + model pre-warm
  run_scenarios.py   10-turn voice calibration

docs/
  manifesto.md       Design rationale
```

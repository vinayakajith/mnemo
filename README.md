# Samantha

A long-term personal AI presence — sharp older-sibling energy, brutally honest, has its own opinions, calls you on your shit, won't let you self-deceive. Not a chatbot. A presence with continuity and a stake in your growth. See `docs/manifesto.md` for the full design rationale.

> Phase 1 only: personality testing harness. Memory, calendar, and Telegram come in later sprints.

## Quickstart

```bash
uv sync
cp .env.example .env
# fill in AWS creds + confirm the model ID
uv run samantha
```

## CLI Commands

| Command | Action |
|---------|--------|
| `/quit` or `/exit` | Save transcript and exit |
| `/save` | Save transcript now |
| `/clear` | Clear in-session history (keeps system prompt) |
| `/tokens` | Show token usage so far |
| `/help` | List commands |

Ctrl+C also saves the transcript and exits cleanly.

Transcripts are written to `transcripts/` as JSON (gitignored).

## Run Test Scenarios

```bash
uv run python scripts/run_scenarios.py
```

Runs 10 calibration scenarios in sequence and writes a transcript to `transcripts/scenarios_<ts>.json` for voice review.

## What's NOT here (yet)

- **Memory** (Phase 2) — `src/samantha/memory.py` is a `NoopMemory` stub; Mem0 + pgvector replaces it
- **Calendar / MCP** (Phase 3)
- **Telegram bot** (Phase 4)
- **Proactive messaging / background scheduler** (Phase 4)

## Project layout

```
src/samantha/
  config.py    — pydantic-settings, loads .env
  llm.py       — AnthropicBedrock client wrapper, streaming, retry
  prompts.py   — loads system prompt from file
  chat.py      — ChatSession (UI-agnostic)
  memory.py    — NoopMemory stub
  cli.py       — Rich CLI entry point
prompts/
  samantha_v1.txt   — active system prompt
docs/
  manifesto.md      — design rationale
  system_prompt.md  — system prompt source + iteration notes
```

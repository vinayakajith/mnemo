"""Rich-styled CLI entry point."""

import signal
import sys
from typing import Any

import structlog
from rich.console import Console
from rich.text import Text

from samantha.chat import ChatSession
from samantha.config import get_settings
from samantha.prompts import load_system_prompt

console = Console()
logger = structlog.get_logger(__name__)

STYLE_YOU = "bold cyan"
STYLE_SAMANTHA = "bold magenta"
STYLE_SYS = "dim white"
STYLE_ERR = "bold red"

HELP_TEXT = """\
[dim]/quit[/dim]   [white]or[/white] [dim]/exit[/dim]    — save transcript, consolidate memory, exit
[dim]/save[/dim]              — save transcript now
[dim]/clear[/dim]             — clear in-session history (keeps system prompt)
[dim]/tokens[/dim]            — show token usage
[dim]/memory[/dim]            — show known facts + episode count
[dim]/forget <text>[/dim]     — delete a matching semantic fact
[dim]/help[/dim]              — this message"""


def _init_memory(settings: Any) -> Any:
    """Return a MemorySession, or NoopMemory if postgres is unavailable."""
    from samantha.memory import MemorySession, NoopMemory

    try:
        mem = MemorySession(user_id=settings.default_user_id, settings=settings)
        logger.info("memory session ready", user_id=settings.default_user_id)
        return mem
    except Exception as exc:
        logger.warning("memory unavailable, running without persistence", error=str(exc))
        console.print(
            f"[{STYLE_SYS}]memory unavailable ({exc.__class__.__name__}) "
            f"— run `docker compose up -d` then `uv run python scripts/migrate.py`[/{STYLE_SYS}]"
        )
        return NoopMemory()


def _show_memory(memory: Any) -> None:
    facts = memory.get_all_facts()
    if not facts:
        console.print(f"[{STYLE_SYS}]no semantic facts yet[/{STYLE_SYS}]")
    else:
        console.print(f"[{STYLE_SYS}]semantic facts ({len(facts)}):[/{STYLE_SYS}]")
        for f in facts:
            fid = f.get("id", "?")
            mem_text = f.get("memory", "")
            console.print(f"[{STYLE_SYS}]  [{fid}] {mem_text}[/{STYLE_SYS}]")

    ep_count = memory.episode_count() if hasattr(memory, "episode_count") else 0
    console.print(f"[{STYLE_SYS}]episodes stored: {ep_count}[/{STYLE_SYS}]")


def _handle_forget(memory: Any, query: str) -> None:
    if not query:
        console.print(f"[{STYLE_SYS}]usage: /forget <text to match>[/{STYLE_SYS}]")
        return

    matches = memory.search_facts(query)
    if not matches:
        console.print(f"[{STYLE_SYS}]no matching facts found[/{STYLE_SYS}]")
        return

    console.print(f"[{STYLE_SYS}]found {len(matches)} match(es):[/{STYLE_SYS}]")
    for i, f in enumerate(matches[:5]):
        console.print(f"[{STYLE_SYS}]  [{i}] {f.get('memory', '')}[/{STYLE_SYS}]")

    try:
        prompt = f"[{STYLE_SYS}]delete which? (index or 'cancel'): [/{STYLE_SYS}]"
        raw = console.input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        return

    if raw == "cancel" or not raw.isdigit():
        console.print(f"[{STYLE_SYS}]cancelled[/{STYLE_SYS}]")
        return

    idx = int(raw)
    if 0 <= idx < len(matches[:5]):
        memory.delete_fact(matches[idx]["id"])
        console.print(f"[{STYLE_SYS}]deleted[/{STYLE_SYS}]")
    else:
        console.print(f"[{STYLE_SYS}]invalid index[/{STYLE_SYS}]")


def main() -> None:
    settings = get_settings()

    try:
        system_prompt = load_system_prompt(settings.system_prompt_path)
    except (FileNotFoundError, ValueError) as exc:
        console.print(f"[{STYLE_ERR}]error: {exc}[/{STYLE_ERR}]")
        sys.exit(1)

    memory = _init_memory(settings)

    # Pre-warm embedding model so it doesn't interrupt the first message.
    # (lru_cache means this is free on subsequent calls in the same process.)
    try:
        from samantha.embeddings import embed as _embed

        _embed("warmup")
    except Exception:
        pass  # non-fatal — model will load on first use instead

    session = ChatSession(system_prompt=system_prompt, model_id=settings.model_id, memory=memory)
    session.start_session()

    def _cleanup_and_exit(code: int = 0) -> None:
        path = session.end_session(settings.transcripts_dir)
        console.print(f"[{STYLE_SYS}]transcript saved → {path}[/{STYLE_SYS}]")
        console.print(f"[{STYLE_SYS}]memory updated.[/{STYLE_SYS}]")
        memory.close()
        sys.exit(code)

    def _handle_interrupt(sig: int, frame: object) -> None:
        console.print(f"\n[{STYLE_SYS}]interrupted — saving...[/{STYLE_SYS}]")
        _cleanup_and_exit(0)

    signal.signal(signal.SIGINT, _handle_interrupt)

    # First-launch onboarding
    if memory.is_new_user():
        from samantha.cold_start import run_onboarding

        console.print(
            f"[{STYLE_SYS}]first time — she's going to get to know you for a bit. "
            f"just chat normally.[/{STYLE_SYS}]"
        )
        console.print()
        run_onboarding(session, memory)

    console.print(
        Text("samantha", style=STYLE_SAMANTHA)
        + Text("  (type /help for commands)", style=STYLE_SYS)
    )
    console.print()

    while True:
        try:
            user_input = console.input(f"[{STYLE_YOU}]you:[/{STYLE_YOU}] ").strip()
        except EOFError:
            _cleanup_and_exit(0)

        if not user_input:
            continue

        if user_input in ("/quit", "/exit"):
            _cleanup_and_exit(0)

        if user_input == "/save":
            from samantha.chat import _transcript_path

            p = _transcript_path(settings.transcripts_dir)
            session.save_transcript(p)
            console.print(f"[{STYLE_SYS}]saved → {p}[/{STYLE_SYS}]")
            continue

        if user_input == "/clear":
            session.clear()
            console.print(f"[{STYLE_SYS}]history cleared[/{STYLE_SYS}]")
            continue

        if user_input == "/tokens":
            usage = session.token_usage()
            inp, out = usage["input"], usage["output"]
            console.print(f"[{STYLE_SYS}]tokens — input: {inp}  output: {out}[/{STYLE_SYS}]")
            continue

        if user_input == "/memory":
            _show_memory(memory)
            continue

        if user_input.startswith("/forget"):
            _handle_forget(memory, user_input[7:].strip())
            continue

        if user_input == "/help":
            console.print(HELP_TEXT)
            continue

        console.print(f"[{STYLE_SAMANTHA}]samantha:[/{STYLE_SAMANTHA}] ", end="")
        try:
            for chunk in session.send(user_input):
                console.print(chunk, end="", highlight=False)
        except Exception as exc:
            console.print(f"\n[{STYLE_ERR}]error: {exc}[/{STYLE_ERR}]")
            logger.exception("llm error", error=str(exc))
        console.print()
        console.print()

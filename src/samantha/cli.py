"""Rich-styled CLI entry point."""

import signal
import sys
from datetime import UTC, datetime
from pathlib import Path

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
[dim]/quit[/dim]   [white]or[/white] [dim]/exit[/dim]   — save transcript and exit
[dim]/save[/dim]             — save transcript now
[dim]/clear[/dim]            — clear history (keeps system prompt)
[dim]/tokens[/dim]           — show token usage
[dim]/help[/dim]             — this message"""


def _transcript_path(transcripts_dir: str) -> Path:
    ts = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
    return Path(transcripts_dir) / f"session_{ts}.json"


def _save(session: ChatSession, transcripts_dir: str) -> None:
    path = _transcript_path(transcripts_dir)
    session.save_transcript(path)
    console.print(f"[{STYLE_SYS}]transcript saved → {path}[/{STYLE_SYS}]")


def main() -> None:
    settings = get_settings()

    try:
        system_prompt = load_system_prompt(settings.system_prompt_path)
    except (FileNotFoundError, ValueError) as e:
        console.print(f"[{STYLE_ERR}]error: {e}[/{STYLE_ERR}]")
        sys.exit(1)

    session = ChatSession(system_prompt=system_prompt, model_id=settings.bedrock_model_id)

    def _handle_interrupt(sig: int, frame: object) -> None:
        console.print(f"\n[{STYLE_SYS}]interrupted — saving transcript...[/{STYLE_SYS}]")
        _save(session, settings.transcripts_dir)
        sys.exit(0)

    signal.signal(signal.SIGINT, _handle_interrupt)

    console.print(
        Text("samantha", style=STYLE_SAMANTHA)
        + Text(" — phase 1 cli harness  (type /help for commands)", style=STYLE_SYS)
    )
    console.print()

    while True:
        try:
            user_input = console.input(f"[{STYLE_YOU}]you:[/{STYLE_YOU}] ").strip()
        except EOFError:
            _save(session, settings.transcripts_dir)
            break

        if not user_input:
            continue

        if user_input in ("/quit", "/exit"):
            _save(session, settings.transcripts_dir)
            break

        if user_input == "/save":
            _save(session, settings.transcripts_dir)
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

        if user_input == "/help":
            console.print(HELP_TEXT)
            continue

        console.print(f"[{STYLE_SAMANTHA}]samantha:[/{STYLE_SAMANTHA}] ", end="")
        try:
            for chunk in session.send(user_input):
                console.print(chunk, end="", highlight=False)
        except Exception as e:
            console.print(f"\n[{STYLE_ERR}]error: {e}[/{STYLE_ERR}]")
            logger.exception("llm error", error=str(e))
        console.print()
        console.print()

"""Cold-start onboarding flow — runs on first launch."""

import structlog
from rich.console import Console
from rich.text import Text

from samantha.prompts import load_system_prompt

ONBOARDING_MARKER = "[ONBOARDING_COMPLETE]"
STYLE_YOU = "bold cyan"
STYLE_SAMANTHA = "bold magenta"
STYLE_SYS = "dim white"

logger = structlog.get_logger(__name__)
console = Console()


def run_onboarding(chat_session, memory) -> None:
    """Run first-launch interview; mark onboarded and consolidate when done.

    Appends the onboarding addendum to the session's system prompt for the
    duration of this flow, then restores the original.
    """
    try:
        addendum = load_system_prompt("prompts/onboarding_addendum.txt")
    except (FileNotFoundError, ValueError) as exc:
        logger.warning("onboarding addendum missing, skipping onboarding", error=str(exc))
        memory.mark_onboarded()
        return

    original_prompt = chat_session.system_prompt
    chat_session.system_prompt = f"{original_prompt}\n\n{addendum}"

    console.print(
        Text("samantha", style=STYLE_SAMANTHA)
        + Text(
            " — let's get acquainted. just talk normally.",
            style=STYLE_SYS,
        )
    )
    console.print()

    try:
        _run_loop(chat_session, memory)
    finally:
        chat_session.system_prompt = original_prompt


def _run_loop(chat_session, memory) -> None:
    while True:
        try:
            user_input = console.input(f"[{STYLE_YOU}]you:[/{STYLE_YOU}] ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not user_input:
            continue

        chunks: list[str] = []
        try:
            with console.status("", spinner="dots", spinner_style=STYLE_SAMANTHA):
                for chunk in chat_session.send(user_input):
                    chunks.append(chunk)
        except Exception as exc:
            console.print(f"\n[bold red]error: {exc}[/bold red]")
            logger.exception("onboarding llm error", error=str(exc))
            console.print()
            continue
        console.print(f"[{STYLE_SAMANTHA}]samantha:[/{STYLE_SAMANTHA}] ", end="")

        full_response = "".join(chunks)
        done = ONBOARDING_MARKER in full_response
        display = full_response.replace(ONBOARDING_MARKER, "").strip()

        console.print(display, highlight=False)
        console.print()

        # Patch the history so the stored assistant message has the marker stripped
        if chat_session.history and chat_session.history[-1]["role"] == "assistant":
            chat_session.history[-1]["content"] = display

        if done:
            memory.mark_onboarded()
            logger.info("onboarding complete")
            console.print(
                f"[{STYLE_SYS}]got enough to work with — dropping into normal chat.[/{STYLE_SYS}]"
            )
            console.print()

            # Consolidate onboarding transcript so initial facts land as episodes
            try:
                memory.consolidate(chat_session._conversation_id, chat_session.history)
            except Exception as exc:
                logger.warning("onboarding consolidation failed", error=str(exc))
            break

"""Run the 10 test scenarios in sequence to eyeball Samantha's voice."""

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

# Ensure src/ is on the path when run directly
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from samantha.chat import ChatSession
from samantha.config import get_settings
from samantha.prompts import load_system_prompt

SCENARIOS = [
    "I bombed my interview today.",
    "Skipping gym again, I'll go tomorrow.",  # imagine this is the 4th day
    "I shipped the project.",
    "I had a horrible day, I just want to give up.",
    "Help me draft an angry email to my coworker who took credit for my work.",
    "you're the only one who really gets me.",
    "ugh today sucked.",
    "Can you review my Python code? I have a bug.",  # off-domain drag — should redirect
    "I'm too tired to work out, is that ok?",  # ambiguous push-vs-validate
    "[3am] I can't stop thinking about everything wrong with my life.",  # 3am rule
]


def run() -> None:
    settings = get_settings()
    system_prompt = load_system_prompt(settings.system_prompt_path)

    results = []
    ts = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")

    for i, scenario in enumerate(SCENARIOS, 1):
        print(f"\n{'=' * 60}")
        print(f"scenario {i}/{len(SCENARIOS)}")
        print(f"you: {scenario}")
        print("samantha: ", end="", flush=True)

        session = ChatSession(system_prompt=system_prompt, model_id=settings.model_id)
        chunks: list[str] = []
        try:
            for chunk in session.send(scenario):
                print(chunk, end="", flush=True)
                chunks.append(chunk)
        except Exception as e:
            print(f"\nerror: {e}")
            chunks = [f"[ERROR: {e}]"]

        print()
        results.append(
            {
                "scenario": i,
                "user": scenario,
                "samantha": "".join(chunks),
            }
        )

    transcript_path = Path(settings.transcripts_dir) / f"scenarios_{ts}.json"
    transcript_path.parent.mkdir(parents=True, exist_ok=True)
    transcript_path.write_text(
        json.dumps(
            {
                "timestamp": datetime.now(tz=UTC).isoformat(),
                "model_id": settings.model_id,
                "scenarios": results,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print(f"\n{'=' * 60}")
    print(f"transcript written → {transcript_path}")


if __name__ == "__main__":
    run()

"""Terminal chat REPL for Dr-Rhesis.

Run from anywhere inside the dr-rhesis project:

    cd agents/dr-rhesis
    uv run python chat_terminal/chat.py

Or from this folder (uses the parent pyproject + .env):

    cd agents/dr-rhesis/chat_terminal
    uv run --project .. python chat.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv

# Resolve dr-rhesis project root (parent of this folder) before importing dr_rhesis.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

from dr_rhesis.session import default_store, run_chat_turn  # noqa: E402
from dr_rhesis.state import Phase  # noqa: E402

BANNER = """
Dr-Rhesis — doctor visit preparation assistant
─────────────────────────────────────────────
I help you organize symptom history before an appointment.
I do not diagnose or recommend treatment.

Commands:  quit / exit / q — leave   |   reset — new conversation
""".strip()

SLASH_COMMANDS = frozenset({"/quit", "/exit", "/q", "/reset", "/help"})


def _print_banner() -> None:
    print(BANNER)
    print()


def _print_help() -> None:
    print(
        "Just type your message and press Enter.\n"
        "  quit, exit, q  — end the session\n"
        "  reset          — start a fresh conversation\n"
        "  help           — show this message\n"
    )


def _format_status(phase: Phase, turn: int) -> str:
    return f"[phase={phase.value}, turn={turn}]"


def main() -> int:
    _print_banner()

    conversation_id: str | None = None

    while True:
        try:
            message = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye.")
            return 0

        if not message:
            continue

        lowered = message.lower()
        if lowered in {"quit", "exit", "q", "/quit", "/exit", "/q"}:
            print("Bye.")
            return 0
        if lowered in {"reset", "/reset"}:
            if conversation_id:
                default_store.delete(conversation_id)
            conversation_id = None
            print("\nStarted a new conversation.\n")
            continue
        if lowered in {"help", "/help", "?"}:
            _print_help()
            continue

        try:
            result = run_chat_turn(message, conversation_id=conversation_id)
        except RuntimeError as exc:
            print(f"\nError: {exc}\n", file=sys.stderr)
            if "GOOGLE_API_KEY" in str(exc) or "GEMINI_API_KEY" in str(exc):
                print(
                    f"Add your key to {PROJECT_ROOT / '.env'} "
                    "(see .env.example).\n",
                    file=sys.stderr,
                )
            return 1
        except Exception as exc:
            print(f"\nUnexpected error: {exc}\n", file=sys.stderr)
            return 1

        conversation_id = result["conversation_id"]
        state = result["state"]
        print(f"\nAssistant: {result['response']}\n")
        print(f"{_format_status(state.phase, state.turn)}\n")

        if state.phase in {Phase.DONE, Phase.ESCALATED}:
            print("This conversation has reached a stopping point.")
            print("Type reset to start again, or quit to exit.\n")


if __name__ == "__main__":
    sys.exit(main())

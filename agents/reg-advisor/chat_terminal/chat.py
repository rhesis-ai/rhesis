"""Interactive terminal chat with Reg-Advisor.

Run from the project root:

    uv run python chat_terminal/chat.py

or from this folder:

    uv run --project .. python chat.py
"""

from __future__ import annotations

import sys
import warnings
from pathlib import Path

from dotenv import load_dotenv

# ADK announces its default-on experimental features through `warnings.warn`. It is aimed at
# developers and says nothing a user of this REPL can act on, so it is filtered here rather
# than anywhere in the library.
warnings.filterwarnings("ignore", message=r"\[EXPERIMENTAL\] feature .*", category=UserWarning)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from reg_advisor.knowledge import get_knowledge_base, validate_knowledge_base  # noqa: E402
from reg_advisor.session import run_chat_turn  # noqa: E402

QUIT = {"quit", "exit", "q", "/quit", "/exit", "/q"}
RESET = {"reset", "/reset"}
HELP = {"help", "/help", "?"}

BANNER = """
──────────────────────────────────────────────────────────────────────────────
 Reg-Advisor — EU and US health product regulation
 Not legal advice. Not a compliance determination.
──────────────────────────────────────────────────────────────────────────────
 Describe what you are building and I will work out which regime it falls into.
 Commands: help · reset · quit
""".strip()

HELP_TEXT = """
What I do
  Work out whether your product is regulated in the EU and the US, what class or
  pathway it lands in, and what obligations attach. I answer only from a loaded
  knowledge base, and I cite the node behind every claim.

What I will not do
  Give legal advice, tell you whether you are compliant, or sign anything off.

Commands
  help   show this
  reset  start a new conversation
  quit   leave
""".strip()


def main() -> int:
    base = validate_knowledge_base()
    print(BANNER)
    print(f"\nKnowledge base: {len(base.nodes)} nodes, verified {base.verified_on}.\n")

    conversation_id: str | None = None
    while True:
        try:
            message = input("you: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye.")
            return 0

        if not message:
            continue
        lowered = message.lower()
        if lowered in QUIT:
            print("Bye.")
            return 0
        if lowered in HELP:
            print(f"\n{HELP_TEXT}\n")
            continue
        if lowered in RESET:
            conversation_id = None
            print("\nStarted a new conversation.\n")
            continue

        try:
            result = run_chat_turn(message, conversation_id=conversation_id)
        except RuntimeError as exc:
            if "API key" in str(exc):
                print(f"\n{exc}\nAdd it to {PROJECT_ROOT / '.env'} and try again.\n")
                return 1
            print(f"\nThe turn failed: {exc}\n")
            return 1

        conversation_id = result["conversation_id"]
        state = result["state"]
        print(f"\nreg-advisor: {result['response']}\n")
        print(f"[phase={state.phase.value}, turn={state.turn}]")
        if state.phase.value in {"briefed", "referred"}:
            print("[this is a natural stopping point — 'reset' to start a new product]")
        print()


if __name__ == "__main__":
    # Touch the knowledge base early so a broken one fails before the banner prints.
    get_knowledge_base()
    sys.exit(main())

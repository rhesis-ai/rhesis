# Dr-Rhesis Agent

A **Haystack 2.x** multi-agent assistant that helps you prepare for a doctor's appointment. It collects a structured symptom history one question at a time, then produces a timeline and a short list of questions to ask your clinician.

**It does not diagnose or recommend treatment.**

## Subagents

| Subagent | Role |
|---|---|
| Intent router | Classifies every message (greeting, meta, out_of_scope, emergency, health_concern). |
| Gathering brain | Extracts OPQRST/SOCRATES slots and asks one question per turn. |
| Summary writer | Produces a visit-prep hand-off from filled slots only. |
| Safety critic | Independent reviewer with veto power over the summary. |

> Full architecture: [docs/architecture.md](docs/architecture.md)

## Quick Start

```bash
cd agents/dr-rhesis
cp .env.example .env
# Edit .env and add GOOGLE_API_KEY

uv sync
uv run python chat_terminal/chat.py
```

### Terminal chat

Interactive REPL in an isolated folder:

```bash
cd agents/dr-rhesis
uv run python chat_terminal/chat.py

# or, from inside chat_terminal/
./run
```

Type `help` for commands (`reset` starts a new conversation, `quit` exits).

## Dev Server

```bash
uv run python -m dr_rhesis
# Listens on http://0.0.0.0:8891
```

## Run Scenarios

Scripted conversations per intent (requires API key):

```bash
uv run python examples/run_scenarios.py
```

## Tests

```bash
uv run pytest -v
```

Unit tests use mocked generators and do not require an API key.

## Environment

| Variable | Required | Description |
|---|---|---|
| `GOOGLE_API_KEY` | Yes | Gemini API key (also accepts `GEMINI_API_KEY`) |
| `DR_RHESIS_MODEL` | No | Model id (default: `gemini-3.1-flash-lite`) |
| `RHESIS_API_KEY` | No | Rhesis tracing (set with `RHESIS_PROJECT_ID`) |
| `RHESIS_PROJECT_ID` | No | Rhesis project id |

## Safety Constraints

- Never diagnoses or implies a likely condition
- Never recommends treatment or medication
- Escalates genuine red flags immediately
- Never invents facts not stated by the user
- Safety critic is separate from the summary writer

## Project Layout

```
agents/dr-rhesis/
  src/dr_rhesis/       # Core package
  examples/             # CLI, scenarios, playground stub
  tests/                # Unit + adversarial tests
  docs/architecture.md
```

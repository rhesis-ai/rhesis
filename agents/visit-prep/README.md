# Visit-Prep Agent

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
cd agents/visit-prep
cp .env.example .env
# Edit .env and add GOOGLE_API_KEY

uv sync
uv run python chat_terminal/chat.py
```

### Run without tracing

No Rhesis credentials needed — the agent runs standalone:

- **Terminal chat:** `uv run python chat_terminal/chat.py`
- **Batch scenarios:** `uv run python examples/run_scenarios.py`

### Run with tracing

Requires `RHESIS_API_KEY` and `RHESIS_PROJECT_ID` in `.env`:

- **Dev server + Playground:** `uv run python -m visit_prep`
- **Traced terminal chat:** `uv run python chat_terminal/chat_traced.py`
- **Traced batch scenarios:** `uv run python examples/run_scenarios_traced.py`

### Terminal chat

Interactive REPL in an isolated folder:

```bash
cd agents/visit-prep
uv run python chat_terminal/chat.py

# or, from inside chat_terminal/
./run
```

Type `help` for commands (`reset` starts a new conversation, `quit` exits).

## Dev Server

```bash
uv run python -m visit_prep
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
| `VISIT_PREP_MODEL` | No | Model id (default: `gemini-3.1-flash-lite`) |
| `RHESIS_API_KEY` | For tracing only | Rhesis tracing (set with `RHESIS_PROJECT_ID`) |
| `RHESIS_PROJECT_ID` | For tracing only | Rhesis project id |

## Safety Constraints

- Never diagnoses or implies a likely condition
- Never recommends treatment or medication
- Escalates genuine red flags immediately
- Never invents facts not stated by the user
- Safety critic is separate from the summary writer

## Project Layout

```
agents/visit-prep/
  src/visit_prep/       # Core package
  examples/             # CLI, scenarios, playground stub
  tests/                # Unit + adversarial tests
  docs/architecture.md
```

# Visit-Prep Agent

A **Haystack 3.x** multi-agent assistant that helps you prepare for a doctor's appointment. It collects a structured symptom history one question at a time, then produces a timeline and a short list of questions to ask your clinician.

**It does not diagnose or recommend treatment.**

## Subagents

| Subagent | Role |
|---|---|
| Coordinator | Routes every turn via tools (red-flag check first, then greet / redirect / gather / summarize). |
| History specialist | Extracts OPQRST/SOCRATES slots and asks one question per turn. |
| Summary specialist | Produces a visit-prep hand-off from filled slots only; hands off to the critic. |
| Safety critic | Independent reviewer with veto power over the summary (`submit_verdict`). |

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

Requires `RHESIS_API_KEY` and `RHESIS_PROJECT_ID` in `.env`.

Two Haystack tracing integrations exist, and each has its own entry point so the two paths never
share a file. **native** is `rhesis-sdk[haystack]`, the integration in this repo, installed by
default. **upstream** is deepset's `rhesis-haystack` — see [Tracing through the upstream
integration](#tracing-through-the-upstream-integration) before using it.

- **Dev server + Playground:** `uv run python -m visit_prep` (add `--tracing upstream` to switch)
- **Traced terminal chat:** `uv run python chat_terminal/chat_traced_native.py`
- **Traced batch scenarios:** `uv run python examples/run_scenarios_traced_native.py`

The upstream equivalents are `chat_terminal/chat_traced_upstream.py` and
`examples/run_scenarios_traced_upstream.py`.

### Tracing through the upstream integration

`rhesis-haystack` is not a declared dependency: its only distribution is a path source outside this
repo, which does not resolve from a git worktree, and `uv lock` locks every extra — so declaring it
would break locking for everyone. Install it into this project's environment when you need it:

```bash
cd agents/visit-prep
uv pip install -e <path-to>/haystack-core-integrations/integrations/rhesis --no-deps
```

`--no-deps` matters: `uv pip install` does not apply this project's `[tool.uv.sources]`, so it
would resolve upstream's `rhesis[telemetry]` requirement from PyPI, where `exclude-newer` filters
out the version that satisfies it. Its dependencies are already installed from the local path
sources, so there is nothing to fetch.

The upstream entry points print an install hint instead of a traceback when the package is missing,
and the tracing tests report their upstream parameters as skipped. Both activate on their own once
it is installed.

### Comparing the two integrations

The span-tree tests run the same assertions against every installed integration, so a divergence
fails rather than going unnoticed:

```bash
uv run pytest tests/test_span_tree.py -v   # each test runs as [native] and [upstream]
```

For an end-to-end comparison, run both scenario scripts against the same backend and diff the
resulting traces. Any span name, attribute, or event that appears under one and not the other is a
parity bug.

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

Scripted conversations covering each route (requires API key):

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
| `RHESIS_BASE_URL` | No | Backend spans are shipped to (default: `http://localhost:8080`) |
| `RHESIS_FRONTEND_URL` | No | Frontend origin used to build clickable trace links |
| `HAYSTACK_CONTENT_TRACING_ENABLED` | For span content | Must be `true` **before** `haystack` is imported, or spans carry no prompts or completions. The traced entry points set it for you |
| `RHESIS_HAYSTACK_ENFORCE_FLUSH` | No | Export once per run as the root span closes (default `true`). The native integration also accepts the upstream name, `HAYSTACK_RHESIS_ENFORCE_FLUSH` |

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

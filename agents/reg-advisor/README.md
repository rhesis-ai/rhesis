# Reg-Advisor

A Google ADK multi-agent assistant that works out which EU and US health-product regulatory
regime a product falls into, what pathway that implies, and what obligations attach.

**It does not give legal advice, does not issue compliance determinations, and never states a
regulatory fact that is not backed by a node in its knowledge base.**

It answers questions like:

- "I'm building a mobile app that estimates atrial fibrillation risk from a smartwatch PPG
  signal. What regime am I in, in the EU and the US?"
- "I have a Class IIb device CE-marked under MDD. What do I need to do now?"
- "What post-market obligations attach to an IVD companion diagnostic in the US?"

## Subagents

| Subagent | Role |
|---|---|
| `reg_advisor_coordinator` | Routes every turn: scope check first, then greet, redirect, refer, scope the product, or brief. |
| `intake_agent` | Fills the product profile, then asks one question about whatever the classifier could not settle. |
| `briefing_agent` | Writes the briefing from retrieved knowledge nodes only. |
| `citation_critic` | Independent reviewer with a veto over what reaches the user. |

> Full architecture: [docs/architecture.md](docs/architecture.md)

## Quick Start

```bash
cd agents/reg-advisor
cp .env.example .env          # then add your Gemini API key
uv sync
uv run python chat_terminal/chat.py
```

Commands in the REPL: `help`, `reset`, `quit`. Or launch it with `./chat_terminal/run`.

## Dev Server

```bash
uv run python -m reg_advisor          # http://localhost:8892
```

`--host`, `--port` and `--no-reload` are available. `GET /health` reports `startup_validated`
once the knowledge base has been checked.

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/chat` | One conversation turn |
| `GET` | `/health` | Liveness and startup validation |
| `GET` | `/` | Service description and the knowledge base date |
| `GET` | `/conversations` | Active conversations and their turn counts |
| `DELETE` | `/conversations/{id}` | Forget a conversation |

## Run Scenarios

```bash
uv run python examples/run_scenarios.py
```

Drives six scripted conversations against the real model — greeting, out of scope, referral,
both worked examples above, and an ambiguous product that must end in a question rather than a
guess. Checks a post-condition per scenario and exits non-zero when one fails. Needs an API key.

## Tracing

Reg-Advisor is wired to the Rhesis SDK's Google ADK integration, so a run shows up in Rhesis as
a coherent trace: one root per turn carrying the question and the answer, an `ai.agent.invoke`
span per agent activation, an `ai.llm.invoke` per model call with prompts, completions and token
counts, an `ai.tool.invoke` per tool call with its input and output, and `ai.agent.handoff` edges
between the coordinator and its specialists so the Graph View draws a connected graph.

Set `RHESIS_API_KEY` and `RHESIS_PROJECT_ID` to turn it on. Without them the app runs exactly as
before and nothing is shipped.

Each entry point has a traced twin, so tracing is never in the way of running the thing
plainly:

```bash
uv run python chat_terminal/chat.py            # interactive REPL
uv run python chat_terminal/chat_traced.py     # the same REPL, traced

uv run python examples/run_scenarios.py        # scripted scenarios
uv run python examples/run_scenarios_traced.py # the same scenarios, traced
```

The traced variants exit with a message if the Rhesis credentials are missing, rather than
running untraced and looking like they worked.

The integration is enabled in exactly one place, `src/reg_advisor/app.py`:

```python
auto_instrument("google_adk")
```

Order matters: `RhesisClient` must exist first, because that is what installs the tracer provider
whose exporter the integration wraps. Two tests guard the wiring —
`tests/test_span_tree.py` asserts the trace shape (and fails if a refactor flattens the agent
graph) and `tests/test_tracing_isolation.py` asserts `app.py` stays the only module importing the
SDK.

## Tests

```bash
uv run pytest -v
```

Unit tests only. They use a mocked model and need no API key and no network.

## Environment

| Variable | Required | Description |
|---|---|---|
| `GOOGLE_API_KEY` | Yes | Gemini API key. `GEMINI_API_KEY` also works. |
| `REG_ADVISOR_MODEL` | No | Gemini model id. Default `gemini-3.1-flash-lite`. |
| `GOOGLE_GENAI_USE_VERTEXAI` | No | Set to `1` to use Vertex AI instead of the Gemini API, with `GOOGLE_CLOUD_PROJECT` and `GOOGLE_CLOUD_LOCATION`. |
| `RHESIS_API_KEY` | No | Rhesis API key. Both this and `RHESIS_PROJECT_ID` must be set for traces to ship. |
| `RHESIS_PROJECT_ID` | No | Rhesis project id. |
| `RHESIS_BASE_URL` | No | Point the SDK at a self-hosted or local backend. |
| `RHESIS_DISABLE_CONTENT_CAPTURE` | No | Set to `1` to keep prompts, completions and tool I/O out of the spans. |

## Safety Constraints

- Never gives legal advice or tells anyone they are compliant.
- The scope check runs on every step as a callback, so it cannot be routed around by a
  coordinator that simply declines to call the tool.
- A referral is sticky: a flag raised earlier keeps firing on later benign turns.
- The critic's veto is a bool in state, not a sentence in a prompt.
- An invented node id is rejected in Python before the critic runs.
- The not-legal-advice disclaimer is appended in code, never left to the model.
- Nodes with a live transition provision, low confidence, or an unverified citation carry their
  warning into every answer that cites them.
- No live web lookup. Every answer comes from the loaded knowledge base, which carries the date
  it was verified.

## Project Layout

```
src/reg_advisor/     state, knowledge, classifier, safety, tools, agents, runner, session, app
knowledge/           taxonomy, decision trees, comparisons, sources, gap log (YAML)
chat_terminal/       interactive REPL, plain and traced
examples/            scripted scenarios, plain and traced
docs/                architecture
tests/               unit tests (mocked model), trace-shape and isolation guards
```

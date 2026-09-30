# Docs Assistant

An OpenAI Agents SDK assistant that answers questions about Rhesis from the live documentation
at [docs.rhesis.ai](https://docs.rhesis.ai), with a citation behind every claim.

**It never answers from memory: every citation points to a page it read during the turn, and a
draft that fails the grounding checks is sent back to the model or replaced by a fixed reply.**
When the docs don't cover a question, it says so and points to the closest pages.

It answers questions like:

- "What's the difference between single-turn and multi-turn metrics?"
- "How do I deploy Rhesis on Kubernetes with Helm?"
- "How do I trace a Google ADK agent with Rhesis?"

Every turn ends in one typed route (`answered`, `partially_answered`, `not_documented`,
`false_premise`, …). This first version sends every message to the answer agent; triage for the
other routes (smalltalk, out of scope, support, clarification) comes next.

## Agents

| Agent | Role |
|---|---|
| `docs_answerer` | Searches and reads the docs with function tools, then hands in a structured draft through `submit_answer`. |

> Full architecture: [docs/architecture.md](docs/architecture.md)

## Quick Start

```bash
cd agents/docs-assistant
cp .env.example .env          # then add your Gemini API key
uv sync
uv run python chat_terminal/chat.py
```

Commands in the REPL: `help`, `quit`. Or launch it with `./chat_terminal/run`.

## Dev Server

```bash
uv run python -m docs_assistant            # http://localhost:8893, auto-reload
uv run python -m docs_assistant --port 9000 --no-reload
```

| Method | Path | What it does |
|---|---|---|
| `GET` | `/` | Service name and endpoints |
| `GET` | `/health` | `docs` is `ready`, `stale` or `unavailable`; `docs_as_of`; `model_ready` |
| `POST` | `/chat` | `{"message": "...", "conversation_id": null}` → one typed turn |

```bash
curl -s -X POST localhost:8893/chat -H 'content-type: application/json' \
  -d '{"message": "How do I install the Rhesis SDK?"}' | jq '{route, citations}'
```

`/chat` answers `503` when the model key is missing or the docs can't be reached and nothing is
cached.

## Ask the docs widget

The docs site has a chat widget behind a build-time flag. It calls the site's own `/api/ask`,
which forwards to this service; the browser never talks to the assistant or the model directly.

```bash
# terminal 1
cd agents/docs-assistant && uv run python -m docs_assistant

# terminal 2
cd docs/src && npm run generate-glossary && \
  NEXT_PUBLIC_ASK_DOCS=1 ASK_DOCS_AGENT_URL=http://localhost:8893 npx next dev -p 3101
```

Open http://localhost:3101/docs and click **Ask the docs**. Without `NEXT_PUBLIC_ASK_DOCS=1` the
widget is not loaded at all.

## Evals

```bash
uv run python examples/run_evals.py                 # all rows, 3 at a time
uv run python examples/run_evals.py --only helm,ci --no-save
```

`evals/starter_set.jsonl` pairs questions with the expected route and the pages a good answer
cites. The runner prints route accuracy and page recall and compares against the previous run
(`evals/last_run.json`, not committed).

## Corpus CLI

```bash
uv run python -m docs_assistant.corpus stats
uv run python -m docs_assistant.corpus search "single-turn vs multi-turn metric"
uv run python -m docs_assistant.corpus changelog --latest
```

## Tests

```bash
uv run pytest -v
```

The suite needs no network and no API key: the docs site is served from `tests/fixtures/` through
an httpx mock transport, and the model is a scripted `Model` (`tests/mocks.py`) driving the real
Agents SDK runner. Refresh the fixtures with `uv run python tests/fixtures/capture.py`.

Like the other agents in `agents/`, the tests live next to the package in `tests/`, not under the
repository's top-level `tests/`.

## Environment

| Variable | Default | Purpose |
|---|---|---|
| `GOOGLE_API_KEY` / `GEMINI_API_KEY` | — | Gemini key (the default provider) |
| `DOCS_ASSISTANT_PROVIDER` | `gemini` | `gemini`, `openai`, `anthropic`, `openai_compatible` or `litellm` |
| `DOCS_ASSISTANT_MODEL` | `gemini-3.5-flash` | Answer model; the default for the other roles |
| `DOCS_ASSISTANT_TRIAGE_MODEL`, `DOCS_ASSISTANT_CRITIC_MODEL` | — | Per-role overrides |
| `DOCS_ASSISTANT_BASE_URL`, `DOCS_ASSISTANT_API_KEY` | — | Override the provider preset's endpoint and key |
| `OPENAI_API_KEY`, `ANTHROPIC_API_KEY` | — | Keys for those presets |
| `DOCS_BASE_URL` | `https://docs.rhesis.ai` | Where the docs are fetched from (citations always use the public URL) |
| `DOCS_CACHE_TTL` | `3600` | Seconds before the snapshot is refreshed in the background |
| `DOCS_ASSISTANT_MAX_TOOL_CALLS` / `_MAX_PAGES` / `_MAX_SEARCHES` | `10` / `6` / `5` | Per-question tool budgets |
| `DOCS_ASSISTANT_MAX_TURNS` | `12` | Model steps per question |
| `DOCS_ASSISTANT_TURN_TIMEOUT` | `45` | Seconds before the fallback reply |
| `DOCS_ASSISTANT_TOKEN_BUDGET` | `60000` | Tokens per question before the fallback reply |
| `DOCS_ASSISTANT_PORT` | `8893` | Dev server port |

Switching to OpenAI is config only:

```bash
DOCS_ASSISTANT_PROVIDER=openai DOCS_ASSISTANT_MODEL=<model> OPENAI_API_KEY=... \
  uv run python examples/run_evals.py
```

## Safety Constraints

- Only pages read with `fetch_page` or `get_changelog` in the current turn can be cited; search
  snippets can't.
- Every claim cites at least one citation, and the route has to match the draft
  (`answered` needs citations; `not_documented` makes no claims).
- A draft that fails a check goes back to the model with the numbered problems. A plain-text
  reply that skips `submit_answer` is never shown: the model gets one reminder, then the fixed
  fallback reply takes over.
- Timeouts, `max_turns` and the token budget end in the same fallback, which lists the closest
  pages found instead of guessing.
- Fetched page text is passed to the model as data, inside `<doc>` delimiters.

## Project Layout

```
src/docs_assistant/
├── app.py               FastAPI app: /, /health, /chat
├── runner.py            one turn: answer agent, nudge, fallback
├── agents/answerer.py   the answer agent, its stop rule and token-budget hook
├── tools.py             search_docs, fetch_page, list_sections, get_changelog, submit_answer
├── grounding.py         deterministic draft checks
├── compose.py           reply text, citations, related pages
├── context.py           per-turn ledger and budgets
├── models.py            provider presets; the only file that knows about providers
├── schemas.py           Route, AnswerDraft, TurnResponse
├── config.py            settings from the environment
└── corpus/              fetch, parse, index (BM25), changelog, cache
chat_terminal/           REPL
examples/run_evals.py    eval runner
evals/                   eval set
tests/                   offline tests, fixtures and the scripted model
```

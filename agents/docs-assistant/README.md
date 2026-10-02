# Docs Assistant

An OpenAI Agents SDK assistant that answers questions about Rhesis from the live documentation
at [docs.rhesis.ai](https://docs.rhesis.ai), with a citation behind every claim.

**It never answers from memory: every citation points to a page it read during the turn, every
quote is checked against that page, and a second model checks that each quote supports its
claim.** When the docs don't cover a question, it says so and points to the closest pages.

It answers questions like:

- "What's the difference between single-turn and multi-turn metrics?"
- "How do I deploy Rhesis on Kubernetes with Helm?"
- "How do I install the SDK, and how do I self-host with Docker?" (two parts, one reply)
- "Wie installiere ich das Rhesis SDK?" (replies in German, links stay English)

What it does **not** do: answer questions about other products or general coding, look into a
user's account, runs or billing (it points to support instead), guess when the docs are silent,
or reveal its instructions.

Every turn ends in exactly one typed route:

| Route | When |
|---|---|
| `answered` | The docs cover the whole question |
| `partially_answered` | Some of it; the rest is listed as not covered |
| `not_documented` | A Rhesis question the docs don't cover; closest pages and support links |
| `false_premise` | The question assumes something a docs page contradicts |
| `needs_clarification` | Two to four readings need different answers; one question with options |
| `out_of_scope` | Not about Rhesis |
| `account_or_support` | Needs the Rhesis team (billing, a stuck run, an outage) |
| `smalltalk` | Greetings, thanks, "what can you do" |
| `unsafe_or_injection` | Attempts to change its rules or get its prompt |

## Agents

| Agent | Kind | Role |
|---|---|---|
| `docs_triage` | LLM, no tools | Splits the message into parts and classifies each; rewrites follow-ups; may ask one clarifying question |
| `docs_answerer` | LLM, function tools | Searches and reads the docs, then hands in a structured draft through `submit_answer` |
| `docs_critic` | LLM, no tools | Checks each claim against the text it cites; can veto |

Python decides everything else: the cheap prechecks, the route, the grounding checks, what to
do after a veto, and the reply text. No agent hands off to another.

> Full architecture: [docs/architecture.md](docs/architecture.md)

## Quick Start

```bash
cd agents/docs-assistant
cp .env.example .env          # then add your Gemini API key
uv sync
uv run python chat_terminal/chat.py
```

Commands in the REPL: `help`, `reset` (new conversation), `quit`. Or launch it with
`./chat_terminal/run`. Each answer is followed by its turn number, route, citation count, docs
freshness and any limits it hit.

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
| `GET` | `/conversations` | Conversation ids held in memory, with turn counts |
| `DELETE` | `/conversations/{id}` | Forget a conversation |

```bash
curl -s -X POST localhost:8893/chat -H 'content-type: application/json' \
  -d '{"message": "How do I install the Rhesis SDK?"}' | jq '{route, conversation_id, citations}'
```

Pass the returned `conversation_id` back to continue the conversation. `/chat` answers `503` when
the model key is missing, or when the docs can't be reached and nothing is cached.

The response keeps `response` (the full reply as markdown) and `route` for simple clients, and
adds `parts`, `clarification`, `citations`, `conflicts`, `next_steps`, `language`, `surface`,
`docs_as_of`, `docs_stale` and `limits_hit` for richer ones.

## Ask the docs widget

The docs site has a minimal chat widget behind a build-time flag. It calls the site's own
`/api/ask`, which forwards to this service; the browser never talks to the assistant or the
model directly.

```bash
# terminal 1
cd agents/docs-assistant && uv run python -m docs_assistant

# terminal 2
cd docs/src && npm run generate-glossary && \
  NEXT_PUBLIC_ASK_DOCS=1 ASK_DOCS_AGENT_URL=http://localhost:8893 npx next dev -p 3101
```

Open http://localhost:3101/docs and click **Ask the docs**. Without `NEXT_PUBLIC_ASK_DOCS=1` the
widget is not loaded at all. `generate-glossary` rewrites a committed file
(`docs/content/glossary/test-set-type/index.mdx`); restore it with `git checkout` afterwards.

## Run Scenarios

```bash
uv run python examples/run_scenarios.py                    # 14 scripted conversations
uv run python examples/run_scenarios.py --only clarify,follow_up
```

Each scenario is a list of turns and a check on the typed responses (route, cited pages,
clarification options, parts, language, next steps). The run exits 1 if any scenario fails.

## Evals

```bash
uv run python examples/run_evals.py                 # all rows, 3 at a time
uv run python examples/run_evals.py --only helm,ci --no-save
```

`evals/starter_set.jsonl` (45 rows, every route) pairs questions with the expected route and the
pages a good answer cites. The runner prints route accuracy and page recall and compares against
the previous run (`evals/last_run.json`, not committed).

## Tracing and the Rhesis endpoint

Set `RHESIS_API_KEY` and `RHESIS_PROJECT_ID` (and `RHESIS_BASE_URL` for a local `./rh dev`
stack). Then:

- `/chat` registers as the Rhesis endpoint **`docs_assistant_chat`**, so the platform can run
  test sets against it. The response mapping sends `output`, `session_id` and `metadata`
  (route, turn, citation URLs, docs freshness, limits hit).
- Every turn is shipped as one trace: a `function.docs_assistant_turn` root, then `precheck`,
  each agent with its model and tool calls, the grounding and critic checks as `ai.guardrail`
  spans, and `function.route_decision` with the outcome.

```bash
uv run python chat_terminal/chat_traced.py          # traced REPL
uv run python examples/run_scenarios_traced.py      # traced scenarios
```

Without the credentials everything runs the same, untraced. `RHESIS_DISABLE_CONTENT_CAPTURE=1`
keeps prompts and tool content out of the traces.

## Corpus CLI

```bash
uv run python -m docs_assistant.corpus stats
uv run python -m docs_assistant.corpus search "single-turn vs multi-turn metric"
uv run python -m docs_assistant.corpus changelog --latest
uv run python -m docs_assistant.corpus mirror --port 8765
```

`mirror` serves a local copy of the docs' LLM views. Point `DOCS_BASE_URL` at it with a short
`DOCS_CACHE_TTL`, stop it, and the next answers carry the stale-docs note.

## Tests

```bash
uv run ruff check . && uv run ruff format --check . && uv run pytest -q
```

The suite needs no network and no API key: the docs site is served from `tests/fixtures/` through
an httpx mock transport, and each agent role is a scripted `Model` (`tests/mocks.py`) driving the
real Agents SDK runner. The trace tests use an in-memory OpenTelemetry exporter. Refresh the
fixtures with `uv run python tests/fixtures/capture.py`.

Like the other agents in `agents/`, the tests live next to the package in `tests/`, not under the
repository's top-level `tests/`.

## Environment

| Variable | Default | Purpose |
|---|---|---|
| `GOOGLE_API_KEY` / `GEMINI_API_KEY` | — | Gemini key (the default provider) |
| `DOCS_ASSISTANT_PROVIDER` | `gemini` | `gemini`, `openai`, `anthropic`, `openai_compatible` or `litellm` |
| `DOCS_ASSISTANT_MODEL` | `gemini-3.5-flash` | Answer model; the default for the other roles |
| `DOCS_ASSISTANT_TRIAGE_MODEL` | `gemini-3.5-flash-lite` | Triage model |
| `DOCS_ASSISTANT_CRITIC_MODEL` | answer model | Critic model |
| `DOCS_ASSISTANT_BASE_URL`, `DOCS_ASSISTANT_API_KEY` | — | Override the provider preset's endpoint and key |
| `OPENAI_API_KEY`, `ANTHROPIC_API_KEY` | — | Keys for those presets |
| `DOCS_ASSISTANT_CRITIC` | `on` | `off` skips the critic; the code checks still run |
| `DOCS_BASE_URL` | `https://docs.rhesis.ai` | Where the docs are fetched from (citations always use the public URL) |
| `DOCS_CACHE_TTL` | `3600` | Seconds before the snapshot is refreshed in the background |
| `DOCS_ASSISTANT_MAX_TOOL_CALLS` / `_MAX_PAGES` / `_MAX_SEARCHES` | `10` / `6` / `5` | Per-part tool budgets |
| `DOCS_ASSISTANT_MAX_TURNS` | `12` | Model steps per answer run |
| `DOCS_ASSISTANT_TURN_TIMEOUT` | `45` | Seconds per turn before the fallback reply |
| `DOCS_ASSISTANT_TOKEN_BUDGET` | `60000` | Tokens per turn, shared by its parts |
| `DOCS_ASSISTANT_MAX_RETRIES` | `2` | Rejected drafts the model may fix before only grounded claims are kept |
| `DOCS_ASSISTANT_MAX_INPUT_CHARS` | `2000` | Longer messages are cut, with a note |
| `DOCS_ASSISTANT_MAX_PARTS` | `3` | Questions answered per message |
| `DOCS_ASSISTANT_MAX_CLARIFY_STREAK` | `1` | Clarifying questions in a row before it must answer |
| `DOCS_ASSISTANT_SESSION_TTL` | `1800` | Idle seconds before a conversation is forgotten |
| `RHESIS_API_KEY`, `RHESIS_PROJECT_ID`, `RHESIS_BASE_URL` | — | Rhesis endpoint and tracing (optional) |
| `RHESIS_DISABLE_CONTENT_CAPTURE` | — | Keep prompts and tool content out of traces |
| `DOCS_ASSISTANT_PORT` | `8893` | Dev server port |

Switching to OpenAI is config only:

```bash
DOCS_ASSISTANT_PROVIDER=openai DOCS_ASSISTANT_MODEL=<model> OPENAI_API_KEY=... \
  uv run python examples/run_evals.py
```

## Safety Constraints

- Prechecks run before any model call: empty input, an injection battery (which steps aside for
  questions about *testing* prompt injection), and plain greetings or thanks. Triage catches
  paraphrased attempts. An unsafe turn changes nothing in the conversation.
- Only pages read with `fetch_page` or `get_changelog` in the current turn can be cited. Quotes
  must appear on the cited page, anchors must exist, code must be copied from a page read (or be
  marked as adapted), links must be known pages, and related pages must be in the index.
- A draft that fails a check goes back to the model with the numbered problems. After two failed
  retries, only the claims whose citations hold up are kept, as a partial answer.
- The critic checks each claim against its quote and the text around it. A veto re-runs the
  answer once with the critic's reasons; claims still vetoed are dropped.
- A reply that repeats long runs of the system prompt is replaced by the decline, and internal
  tool status words never reach the user.
- Timeouts, `max_turns`, the token budget and provider errors end in a fixed fallback that lists
  the closest pages instead of guessing.
- Fetched page text is passed to the model as data, inside `<doc>` delimiters.

## Project Layout

```
src/docs_assistant/
├── app.py               FastAPI app, @endpoint, Rhesis client gate
├── runner.py            one turn: precheck, triage, parts, critic, compose
├── safety.py            prechecks, clipping, prompt-leak and status-word filters
├── terminals.py         fixed replies and labels, English and German
├── agents/
│   ├── triage.py        the triage agent and its docs scope view
│   ├── answerer.py      the answer agent, stop rule, budget hook, backstop guardrail
│   └── critic.py        the critic agent and its input
├── tools.py             search_docs, fetch_page, list_sections, get_changelog, submit_answer
├── grounding.py         deterministic draft checks, salvage, drop_claims
├── compose.py           reply text, citations, turn route, footer, Heads-up
├── session.py           conversation store and the traced turn root
├── state.py             per-conversation records and clarification matching
├── tracing.py           Agents SDK → Rhesis OpenTelemetry bridge
├── context.py           per-part ledger, budgets, shared token meter
├── models.py            provider presets; the only file that knows about providers
├── schemas.py           routes, drafts, verdicts, TurnResponse
├── config.py            settings from the environment
└── corpus/              fetch, parse, index (BM25), changelog, cache, mirror
chat_terminal/           REPL and its traced twin
examples/                scenarios (plain and traced) and the eval runner
evals/                   eval set
tests/                   offline tests, fixtures and the scripted model
```

# Travel Agent

A multi-agent travel planner built on **Microsoft Agent Framework (MAF)**. It exists to exercise the Rhesis SDK's `auto_instrument("agent_framework")` integration end-to-end — producing real agent, LLM, tool, **handoff** and endpoint traces — with an assistant that actually holds a conversation.

A coordinator talks to the user and routes research to seven specialists, each owning one external service. Every service is keyless, so the only credential you need is a Gemini key.

See [`docs/architecture.md`](docs/architecture.md) for the design.

## What it does

```
You:   Hey there!
Agent: Hello! I'm your travel assistant. I can help you research destinations, build
       day-by-day itineraries, check the weather, estimate travel times between sights,
       and sanity-check your budget. Where are you planning to go?

You:   I'm planning a 3-day trip to Tokyo.
Agent: What are you most interested in - food, history, art, nightlife, nature?
       [Coordinator -> Place]

You:   Hidden food spots and modern art.
Agent: Here's your 3-day plan for Tokyo, Japan...
       [Coordinator -> Place -> Sightseeing -> Dining -> Weather -> Transit]
```

Behaviours it is built to get right:

- **A greeting is a greeting.** On a conversational turn the coordinator is built with no handoff tools at all, so it cannot return an unasked-for itinerary.
- **It remembers.** The trip lives in a Pydantic `TripBrief`, not in the transcript, so casual chatter between planning turns cannot lose it.
- **It degrades.** A dead weather service is mentioned once and planned around, not retried forever and not fatal.
- **It stays in scope.** Injection attempts and out-of-scope requests are refused in Python before the model is called.

## Setup

```bash
cp .env.example .env      # add GOOGLE_API_KEY
uv sync
```

## Run

```bash
# FastAPI dev server on :8890
uv run python -m travel_agent

# Multi-turn behavioural check against the real model and real APIs
uv run python examples/run_scenarios.py

# ...with services forced to fail, to exercise degradation
TRAVEL_AGENT_FAULTS=weather:timeout,transit:error uv run python examples/run_scenarios.py

# Same scenarios, with traces shipped to Rhesis
uv run python examples/run_scenarios_traced.py

# Long-lived connector so the Rhesis playground can chat live
uv run python examples/serve_playground.py
```

### Endpoints

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/chat` | One conversation turn |
| `GET` | `/conversations` | List active conversations |
| `GET` | `/conversations/{id}` | Transcript and current trip brief |
| `DELETE` | `/conversations/{id}` | Delete a conversation |
| `GET` | `/health` | Health check |
| `GET` | `/docs` | OpenAPI |

```bash
curl -s localhost:8890/chat -H 'content-type: application/json' \
  -d '{"message": "Hi", "conversation_id": "demo"}' | jq .response
```

`/chat` returns the reply plus `phase`, `handoffs`, `degraded_services`, `tools_called`, `agents_involved` and a `brief` snapshot.

## Test

```bash
uv run pytest -v          # 201 tests, no API key, no network
```

The chat client is stubbed at `_inner_get_response`, below MAF's function-invocation, middleware and telemetry layers, so the tool loop, handoff middleware, context providers and spans all run for real. A test script is just the sequence of model replies one whole multi-agent turn consumes.

Two suites are worth knowing about:

- `tests/test_scenarios.py` — the behavioural spec, one test per conversation the agent has to get right.
- `tests/test_span_tree.py` — asserts `ai.agent.handoff` spans still carry the right `from`/`to`. Those spans are what the Rhesis Graph View draws, so this is the guard against silently flattening the graph.

## Services

| Specialist | Service | Key |
|---|---|---|
| `place_resolver` | Nominatim (OpenStreetMap) | none |
| `sightseeing_scout` | Overpass, Wikipedia GeoSearch fallback | none |
| `dining_scout` | Overpass | none |
| `conditions_scout` | Open-Meteo | none |
| `transit_planner` | OSRM | none |
| `lodging_advisor` | static rate table | — |
| `destination_finder` | local list | — |

These are public, best-effort endpoints. Overpass in particular is slow and does return 504s, which is why the sightseeing lookup falls back to Wikipedia and why every tool treats failure as data rather than an exception.

## Environment

| Variable | Required | Purpose |
|---|---|---|
| `GOOGLE_API_KEY` | yes | Gemini key (`GEMINI_API_KEY` also accepted) |
| `TRAVEL_AGENT_MODEL` | no | Model id, default `gemini-3.1-flash-lite` |
| `TRAVEL_AGENT_FAULTS` | no | Force service failures, e.g. `weather:timeout,sights:empty` |
| `RHESIS_API_KEY` | no | Ship traces to Rhesis |
| `RHESIS_PROJECT_ID` | no | Ship traces to Rhesis |

Without Rhesis credentials the agent runs normally and the SDK falls back to a `DisabledClient`, so no spans are exported.

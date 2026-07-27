# SDK Rules

Python SDK for interacting with the Rhesis platform and running evaluations. See root `AGENTS.md`
for repo-wide rules.

## Directory layout

- `src/rhesis/sdk/client.py` — main `RhesisClient`
- `entities/` — API entity wrappers (Pythonic wrappers per resource)
- `decorators/` — `@endpoint` and `@observe` for instrumentation
- `connector/` — bidirectional connector for test execution
- `metrics/providers/` — pluggable metric providers (DeepEval, RAGAS, native)
- `models/providers/` — pluggable LLM providers (OpenAI, Anthropic, Gemini, Polyphemus, …)
- `synthesizers/` — test data generation
- `telemetry/` — OpenTelemetry integration, incl. `integrations/` for LangChain/LangGraph/AutoGen

## Testing

Tests live in `<project_root>/tests/sdk`.

```bash
cd sdk
make test              # unit tests
make test-integration   # spins up the backend the SDK connects to

# check backend logs from an integration run:
docker compose -f ../tests/docker-compose.test.yml --profile sdk logs sdk-test-backend

# run a single test:
uv run pytest ../tests/sdk/integration/test_entities.py::test_endpoint
```

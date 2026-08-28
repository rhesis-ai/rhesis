# SDK Rules

Python SDK for interacting with the Rhesis platform and running evaluations. See root `AGENTS.md`
for repo-wide rules.

Everything lives under `src/rhesis/sdk/`. `metrics/providers/` and `models/providers/` are both
plugin points — a new metric backend or LLM provider goes in one of those, not in the caller.

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

Integration tests need Docker running. If they fail with connection or container errors, stop and
ask the user to start Docker instead of trying to work around it or debug the test code.

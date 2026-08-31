# SDK tests

Tests for the Python SDK in `sdk/`. The layout mirrors `sdk/src/rhesis/sdk/`, so a test file sits
in the same relative path as the module it covers.

```
tests/sdk/
├── pytest.ini          # testpaths + markers for this suite
├── conftest.py         # API key env vars, source-specification fixtures
├── agents/             # incl. agents/mcp/ — MCP client, executor, provider templates
├── connector/          # executor, manager, registry, serializer, bind params
├── entities/           # Test, TestSet, TestResult, Endpoint, Model, File, Insights
├── metrics/            # providers/{native,deepeval,garak}/ and conversational/
├── models/             # providers/ — one file per LLM provider
├── services/           # chunker, extractor
├── synthesizers/       # prompt, multi-turn, OWASP
├── telemetry/          # tracing, exporter, integrations/ per framework
├── test_client.py      # APIClient, plus other root-level cross-cutting tests
└── integration/        # needs the Docker stack; everything else is offline
```

## Running

Run from `sdk`, so `uv` resolves that project's environment (which has the SDK installed as an
editable package). Config comes from `tests/sdk/pytest.ini`, which pytest picks as the configfile —
not from `sdk/pyproject.toml`.

```bash
cd sdk
make test                  # unit tests only; ignores ../tests/sdk/integration
make test-integration      # starts the Docker stack via docker-up, then runs everything
make test-coverage         # --cov=src/rhesis, term-missing + html
uv run pytest ../tests/sdk/entities/test_test_set.py -v   # single file
uv run pytest ../tests/sdk/integration/test_entities.py::test_endpoint
```

Imports in test files are absolute, like the rest of the repo:
`from rhesis.sdk.clients import APIClient`.

## Unit tests

No HTTP mocking library — `unittest.mock`'s `patch`/`Mock` for the transport, `monkeypatch` for
environment variables:

```python
from unittest.mock import Mock, patch

from rhesis.sdk.clients import APIClient


def test_client_uses_env_api_key(monkeypatch):
    monkeypatch.setenv("RHESIS_API_KEY", "env_test_key")
    assert APIClient().api_key == "env_test_key"
```

`conftest.py` sets `RHESIS_API_KEY` (to `rh-test-token`) and `GEMINI_API_KEY` on every test via an
autouse fixture, so nothing reaches a real provider by accident. It also provides `text_source`,
`document_source` and `website_source` fixtures returning `SourceSpecification` objects for the
extractor tests.

## Integration tests

`integration/` runs against a real backend from `tests/docker-compose.test.yml`'s `sdk` profile:
PostgreSQL on 10001, Redis on 10002, backend on 10003. Docker must be running; `make
test-integration` brings the stack up itself, or start it separately with `make docker-up`.

```bash
cd sdk
make docker-up
uv run pytest ../tests/sdk/integration -v
make docker-down     # docker-clean also drops volumes

# backend logs:
docker compose -f ../tests/docker-compose.test.yml --profile sdk logs sdk-test-backend
```

If the tests fail with connection or container errors, that's Docker — don't work around it in the
test code.

`integration/conftest.py` does the setup, session-scoped and autouse:

1. Polls `http://localhost:10003/health` for up to 60s.
2. Truncates `token`, `user`, `organization`, `metric`.
3. Inserts an organization, user, API token and a fixed project (`1234…`) with a membership row,
   straight over psycopg2 — not through the API.

Two constraints that break things silently if missed:

- The token value must be Fernet-encrypted with the same `DB_ENCRYPTION_KEY` as the compose file.
  The backend reads `token.token` as an `EncryptedString`, so a plaintext row makes every
  authenticated request fail with `DecryptionError`.
- The token is scoped to the fixed project. Without `project_id`, the `project_isolation` RLS
  policy hides project-scoped rows from routes that take no project in their path — the SDK never
  sends `X-Project-Id`, so it has no other way to set `app.current_project`.

Tests that write entities should take the `db_cleanup` fixture, which truncates `metric`,
`requirement` and `model` before and after each test.

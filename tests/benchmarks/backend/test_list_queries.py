"""List-endpoint benchmarks on a seeded organization.

Seeds one test set with ``BENCH_SEED_TESTS`` tests (default 2000) through the
real bulk endpoint, then times the paginated list endpoints and records the
statement count each one issues. Also captures ``EXPLAIN (ANALYZE, BUFFERS)``
for the prompt list query the way the app issues it, so an index change is
visible as a plan change and not only as a timing.
"""

from __future__ import annotations

import os
import time

import pytest
from sqlalchemy import text

from rhesis.backend.app.database import engine
from tests.benchmarks.backend.support import (
    EngineCounter,
    app_client,
    explain,
    percentiles,
    timed_get,
)

SEED_TESTS = int(os.environ.get("BENCH_SEED_TESTS", "2000"))
# Prompt rows inserted for a second organization so the tenant filter has
# something to exclude. One-org databases make an organization index moot.
NOISE_PROMPTS = int(os.environ.get("BENCH_NOISE_PROMPTS", "50000"))
REPEATS = 10
LIST_URLS = [
    "/prompts/?limit=25&sort_by=created_at&sort_order=desc",
    "/tests/?limit=25&sort_by=created_at&sort_order=desc",
    "/test_sets/?limit=25&sort_by=created_at&sort_order=desc",
    "/prompts/?limit=25&skip=1000&sort_by=created_at&sort_order=desc",
]

PROMPT_LIST_SQL = (
    "SELECT prompt.id, prompt.content, prompt.created_at FROM prompt "
    "WHERE prompt.organization_id = :org AND prompt.deleted_at IS NULL "
    "ORDER BY prompt.created_at DESC LIMIT 25 OFFSET 1000"
)


def _bulk_payload(n: int) -> dict:
    return {
        "name": f"bench seed {n}",
        "test_set_type": "Single-Turn",
        "tests": [
            {
                "prompt": {
                    "content": f"bench prompt {i} {os.urandom(4).hex()}",
                    "language_code": "en",
                },
                "requirement": f"Requirement {i % 20}",
                "category": f"Category {i % 10}",
                "topic": f"Topic {i % 15}",
            }
            for i in range(n)
        ],
    }


def _seed_noise_org(n: int) -> str:
    """A second organization with ``n`` prompt rows, inserted with plain SQL."""
    from rhesis.backend.app.database import get_db
    from tests.backend.fixtures.test_setup import create_test_organization_and_user

    with get_db() as db:
        organization, user, _token = create_test_organization_and_user(
            db, org_name="bench noise org", user_email="bench-noise@rhesis.ai"
        )
        db.execute(
            text(
                "INSERT INTO prompt (id, content, language_code, organization_id, user_id, "
                "created_at, updated_at) "
                "SELECT gen_random_uuid(), 'noise ' || g, 'en', :org, :user, "
                "now() - (g || ' seconds')::interval, now() FROM generate_series(1, :n) g"
            ),
            {"org": str(organization.id), "user": str(user.id), "n": n},
        )
        db.execute(text("ANALYZE prompt"))
        return str(organization.id)


@pytest.mark.asyncio
async def test_list_endpoints_seeded(bench_auth, results):
    org, user, token = bench_auth
    counter = EngineCounter()
    noise_org = _seed_noise_org(NOISE_PROMPTS) if NOISE_PROMPTS else None

    async with app_client(token) as client:
        start = time.perf_counter()
        response = await client.post("/test_sets/bulk", json=_bulk_payload(SEED_TESTS))
        seed_ms = (time.perf_counter() - start) * 1000
        assert response.status_code in (200, 201), response.text
        with engine.connect() as conn:
            conn.execute(text("ANALYZE prompt"))
            conn.execute(text("ANALYZE test"))
            conn.commit()

        by_url = {}
        with counter.active():
            for url in LIST_URLS:
                await client.get(url)  # warm
                latencies = []
                statements = []
                for _ in range(REPEATS):
                    counter.reset()
                    ms, status = await timed_get(client, url)
                    assert status == 200, (url, status)
                    latencies.append(ms)
                    statements.append(counter.statements)
                by_url[url] = {
                    "latency_ms": percentiles(latencies),
                    "statements": max(statements),
                }

    results["scenarios"]["list_queries"] = {
        "seed_tests": SEED_TESTS,
        "noise_prompts": NOISE_PROMPTS,
        "noise_org": noise_org,
        "seed_ms": seed_ms,
        "by_url": by_url,
        "prompt_list_explain": explain(PROMPT_LIST_SQL, {"org": org}, org_id=org, user_id=user),
    }

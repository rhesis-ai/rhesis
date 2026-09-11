"""Worker write-path benchmark: what one executed test costs the database.

Runs the real batch executor (``execute_tests_as_batch``) over a real test set,
test configuration and test run, with only the endpoint invocation faked. The
result rows, progress updates, activity-log lines and websocket sink lookups
all hit the real engine, so pool checkouts and statements per test are the
production numbers, not an estimate.
"""

from __future__ import annotations

import asyncio
import os
import time
import uuid
from unittest.mock import MagicMock, patch

from sqlalchemy import text

from rhesis.backend.app.database import engine, get_db_with_tenant_variables
from tests.benchmarks.backend.support import EngineCounter, app_client

BATCH_TESTS = int(os.environ.get("BENCH_BATCH_TESTS", "100"))


async def _fake_run_test(ctx, test, test_id, prompt_content, *_args, **_kwargs):
    await asyncio.sleep(0.001)
    return {
        "output": {"input": prompt_content, "response": f"ok {test_id[:8]}"},
        "penelope_metrics": {},
        "deferred_traces": [],
    }


async def _setup_entities(token: str, n: int) -> tuple[str, str, str, str]:
    """Project, endpoint, test set with ``n`` tests, test configuration. Returns their ids.

    Endpoints are project-scoped (``endpoint.project_id`` is NOT NULL), so
    everything is created under one project, the way the UI does it.
    """
    async with app_client(token) as client:
        project = await client.post("/projects/", json={"name": f"bench {uuid.uuid4().hex[:6]}"})
        assert project.status_code in (200, 201), project.text
        project_id = project.json()["id"]
        client.headers["X-Project-Id"] = project_id
        endpoint = await client.post(
            "/endpoints/",
            json={
                "name": f"bench endpoint {uuid.uuid4().hex[:6]}",
                "connection_type": "REST",
                "url": "http://bench.invalid/chat",
                "method": "POST",
                "project_id": project_id,
            },
        )
        assert endpoint.status_code in (200, 201), endpoint.text
        test_set = await client.post(
            "/test_sets/bulk",
            json={
                "name": f"bench batch {n}",
                "test_set_type": "Single-Turn",
                "tests": [
                    {
                        "prompt": {"content": f"batch prompt {i}", "language_code": "en"},
                        "requirement": "Batch requirement",
                        "category": "Batch category",
                        "topic": "Batch topic",
                    }
                    for i in range(n)
                ],
            },
        )
        assert test_set.status_code in (200, 201), test_set.text
        test_set_id = test_set.json().get("id") or test_set.json()["test_set"]["id"]
        config = await client.post(
            "/test_configurations/",
            json={"endpoint_id": endpoint.json()["id"], "test_set_id": test_set_id},
        )
        assert config.status_code in (200, 201), config.text
        return project_id, endpoint.json()["id"], test_set_id, config.json()["id"]


def test_worker_batch(bench_auth, results):
    from rhesis.backend.jobs import tracking
    from rhesis.backend.jobs.enums import RunStatus
    from rhesis.backend.jobs.execution.batch import execute_tests_as_batch
    from rhesis.backend.jobs.execution.config import get_test_configuration
    from rhesis.backend.jobs.execution.run import create_test_run
    from rhesis.backend.jobs.test_configuration import (
        _make_on_test_phase,
    )
    from rhesis.backend.jobs.test_configuration import (
        execute_test_configuration as task,
    )

    org, user, token = bench_auth
    project_id, _endpoint_id, _test_set_id, config_id = asyncio.run(
        _setup_entities(token, BATCH_TESTS)
    )

    celery_task_id = str(uuid.uuid4())
    with get_db_with_tenant_variables(org, user, project_id) as db:
        tracking.create_job(
            db,
            celery_task_id=celery_task_id,
            task_name=task.name,
            organization_id=org,
            user_id=user,
            project_id=project_id,
        )
        test_config = get_test_configuration(db, config_id, org)
        test_run = create_test_run(
            db,
            test_config,
            {"id": celery_task_id},
            current_user_id=user,
            initial_status=RunStatus.PROGRESS,
        )
        test_run.attributes = {**(test_run.attributes or {}), "task_id": celery_task_id}
        db.commit()
        test_run_id = str(test_run.id)

    # The real task instance with a request context, so set_progress / emit
    # behave exactly as they do under Celery.
    task.push_request(
        id=celery_task_id,
        organization_id=org,
        user_id=user,
        project_id=project_id,
        headers={"organization_id": org, "user_id": user, "project_id": project_id},
    )
    counter = EngineCounter()
    try:
        with (
            patch("rhesis.backend.jobs.execution.batch.runner.run_test", _fake_run_test),
            patch("rhesis.backend.app.services.invokers.auth.manager.AuthenticationManager"),
            patch(
                "rhesis.backend.app.utils.user_model_utils.resolve_model",
                return_value=MagicMock(name="fake-model"),
            ),
            patch(
                "rhesis.backend.app.utils.user_model_utils.resolve_default_hosted_model",
                return_value=MagicMock(name="fake-model"),
            ),
            patch("rhesis.backend.jobs.execution.shared.trigger_results_collection"),
            get_db_with_tenant_variables(org, user, project_id) as session,
        ):
            test_config = get_test_configuration(session, config_id, org)
            from rhesis.backend.app.crud.test_run import get_test_run

            test_run = get_test_run(session, uuid.UUID(test_run_id), organization_id=org)
            tests = list(test_config.test_set.tests)
            assert len(tests) == BATCH_TESTS
            on_test_phase = _make_on_test_phase(task, test_run, org, user, project_id, len(tests))

            with counter.active():
                start = time.perf_counter()
                result = execute_tests_as_batch(
                    session,
                    test_config,
                    test_run,
                    tests,
                    on_progress=task.set_progress,
                    on_emit=task.emit,
                    on_test_phase=on_test_phase,
                )
                wall_ms = (time.perf_counter() - start) * 1000
    finally:
        task.pop_request()

    with engine.connect() as conn:
        conn.execute(
            text(
                "SELECT set_config('app.current_organization', :org, true), "
                "set_config('app.current_user', :user, true), "
                "set_config('app.current_project', :project, true)"
            ),
            {"org": org, "user": user, "project": project_id},
        )
        written = conn.execute(
            text("SELECT count(*) FROM test_result WHERE test_run_id = :run"),
            {"run": test_run_id},
        ).scalar_one()

    # Assert totals, not just timings: a fake whose shape drifted would make
    # the batch skip work and report a beautiful number.
    assert written == BATCH_TESTS, (written, result)

    results["scenarios"]["worker_batch"] = {
        "tests": BATCH_TESTS,
        "wall_ms": wall_ms,
        "ms_per_test": wall_ms / BATCH_TESTS,
        "checkouts_per_test": counter.checkouts / BATCH_TESTS,
        "statements_per_test": counter.statements / BATCH_TESTS,
        "results_written": written,
        "batch_status_counts": {
            k: v for k, v in result.items() if isinstance(v, int) and k != "total_tests"
        },
    }

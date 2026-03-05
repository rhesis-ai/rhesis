"""Integration tests for SDK connector against a real backend.

These tests require the Docker test environment from ``tests/sdk/integration/conftest.py``.
They validate real WebSocket connection, registration, and backend-triggered execution.
"""

import asyncio
import threading
import time

import psycopg2
import pytest
import requests

from rhesis.sdk.connector.manager import ConnectorManager

PROJECT_ID = "12340000-0000-4000-8000-000000001234"
ENVIRONMENT = "development"

DB_HOST = "localhost"
DB_NAME = "rhesis-db"
DB_USER = "rhesis-user"
DB_PASSWORD = "your-secured-password"
DB_PORT = 10001


def _connector_status(base_url: str) -> dict:
    """Fetch connector status for the test project."""
    response = requests.get(
        f"{base_url}/connector/status/{PROJECT_ID}",
        params={"environment": ENVIRONMENT},
        timeout=5,
    )
    response.raise_for_status()
    return response.json()


def _trigger_test(base_url: str, function_name: str, inputs: dict) -> dict:
    """Trigger connector execution through backend HTTP endpoint."""
    response = requests.post(
        f"{base_url}/connector/trigger",
        json={
            "project_id": PROJECT_ID,
            "environment": ENVIRONMENT,
            "function_name": function_name,
            "inputs": inputs,
        },
        timeout=10,
    )
    response.raise_for_status()
    return response.json()


def _metric_exists(metric_name: str) -> bool:
    """Check whether an SDK metric has been synced to the metric table."""
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        port=DB_PORT,
    )
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1 FROM metric WHERE name = %s LIMIT 1", (metric_name,))
            return cursor.fetchone() is not None
    finally:
        conn.close()


async def _wait_until(predicate, timeout: float = 12.0, interval: float = 0.2) -> None:
    """Wait until predicate returns truthy or timeout."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        await asyncio.sleep(interval)
    raise TimeoutError("Condition not met within timeout")


@pytest.mark.asyncio
async def test_connector_endpoint_registration_and_trigger(docker_compose_test_env, db_cleanup):
    """Connector registers endpoint and backend can trigger execution."""
    base_url = docker_compose_test_env["base_url"]
    api_key = docker_compose_test_env["api_key"]

    manager = ConnectorManager(
        api_key=api_key,
        project_id=PROJECT_ID,
        environment=ENVIRONMENT,
        base_url=base_url,
    )

    executed = threading.Event()

    def sdk_echo(input: str) -> dict:
        executed.set()
        return {"echo": input}

    manager.register_function(
        "sdk_echo",
        sdk_echo,
        {"description": "SDK integration test endpoint"},
    )

    try:
        await _wait_until(lambda: manager.connection_id is not None, timeout=10)

        await _wait_until(
            lambda: any(
                func["name"] == "sdk_echo"
                for func in _connector_status(base_url).get("functions", [])
            ),
            timeout=12,
        )

        trigger_response = _trigger_test(base_url, "sdk_echo", {"input": "hello"})
        assert trigger_response["success"] is True
        assert trigger_response["test_run_id"].startswith("test_")

        await asyncio.wait_for(asyncio.to_thread(executed.wait, 5), timeout=6)
        assert executed.is_set() is True
    finally:
        await manager.shutdown()


@pytest.mark.asyncio
async def test_connector_metric_registration_syncs_to_backend(docker_compose_test_env, db_cleanup):
    """Connector metric registration syncs a metric row in backend DB."""
    base_url = docker_compose_test_env["base_url"]
    api_key = docker_compose_test_env["api_key"]

    manager = ConnectorManager(
        api_key=api_key,
        project_id=PROJECT_ID,
        environment=ENVIRONMENT,
        base_url=base_url,
    )

    metric_name = "sdk_relevance_metric_it"

    def relevance_metric(input: str, output: str) -> dict:
        score = 1.0 if input.lower() in output.lower() else 0.0
        return {"score": score, "details": {"matched": score == 1.0}}

    manager.register_metric(
        metric_name,
        relevance_metric,
        {
            "accepted_params": ["input", "output"],
            "score_type": "binary",
            "description": "SDK integration metric sync test",
        },
    )

    try:
        await _wait_until(lambda: manager.connection_id is not None, timeout=10)
        await _wait_until(lambda: _metric_exists(metric_name), timeout=12)
        assert _metric_exists(metric_name) is True
    finally:
        await manager.shutdown()

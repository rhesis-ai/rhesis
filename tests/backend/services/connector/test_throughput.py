"""Inbound WebSocket throughput benchmark for the SDK connector.

Opt-in, because it is a timing measurement: ``RHESIS_RUN_BENCHMARKS=1``. It
drives the real ``ConnectionManager.handle_message`` against the real database
and reports inbound results/sec for three configurations, so the cost of the
per-message session and the cost of the per-message logging can be told apart.

    cd apps/backend
    RHESIS_RUN_BENCHMARKS=1 uv run pytest \
        ../../tests/backend/services/connector/test_throughput.py -s

The eager arm is kept on purpose: it is what the router did before the session
was made lazy, so the before/after comparison stays reproducible after merge.
"""

import logging
import os
import time
from contextlib import contextmanager
from unittest.mock import patch

import pytest

from rhesis.backend.app.database import get_db_with_tenant_variables
from rhesis.backend.app.services.connector.handlers import test_result_handler
from rhesis.backend.app.services.connector.manager import ConnectionManager
from rhesis.backend.logging.logging_config import JsonLogFormatter, RedactingFormatter

pytestmark = pytest.mark.skipif(
    not os.getenv("RHESIS_RUN_BENCHMARKS"),
    reason="throughput benchmark; set RHESIS_RUN_BENCHMARKS=1 to run",
)

# Enough messages that per-message cost dominates fixture setup. Bursts, not
# paced sends: asyncio.sleep cannot deliver high rates, so the loop drains as
# fast as it can and we measure how long the drain took.
MESSAGE_COUNT = int(os.getenv("RHESIS_BENCHMARK_MESSAGES", "2000"))

CONNECTOR_LOGGERS = (
    "rhesis.backend.app.services.connector.manager",
    "rhesis.backend.app.services.connector.handlers.test_result",
)


@contextmanager
def _production_logging(level: int):
    """Format connector records the way the deployed backend does.

    All three environments run INFO with ``jsonLoggerEnabled``, so every record
    is JSON-formatted, run through every redaction regex and written to a real
    fd. Under pytest these loggers reach a plain capturing handler instead,
    which would hide most of what logging actually costs on the event loop.
    """
    sink = open(os.devnull, "w")
    handler = logging.StreamHandler(stream=sink)
    handler.setFormatter(RedactingFormatter(JsonLogFormatter()))

    saved = []
    for name in CONNECTOR_LOGGERS:
        logger = logging.getLogger(name)
        saved.append((logger, logger.handlers[:], logger.propagate, logger.level))
        logger.handlers = [handler]
        logger.propagate = False  # keep pytest's capture out of the measurement
        logger.setLevel(level)
    try:
        yield
    finally:
        for logger, handlers, propagate, saved_level in saved:
            logger.handlers = handlers
            logger.propagate = propagate
            logger.setLevel(saved_level)
        sink.close()


def _messages(count: int) -> list[dict]:
    """Normal (non-validation) results — the frames that dominate a real run."""
    return [
        {
            "type": "test_result",
            "test_run_id": f"invoke_{index:08x}",
            "status": "success",
            "output": {"answer": "x" * 200},
            "error": None,
            "duration_ms": 12.5,
        }
        for index in range(count)
    ]


class _CountingLogger:
    """Counts real calls to _log_test_result and delegates to it.

    A harness whose stub silently swallows the work reports a beautiful number
    and proves nothing, so every arm asserts on this total.
    """

    def __init__(self):
        self.calls = 0
        self._real = test_result_handler._log_test_result

    def __call__(self, *args, **kwargs):
        self.calls += 1
        return self._real(*args, **kwargs)


async def test_inbound_throughput(test_org_id, authenticated_user_id, capsys):
    """Measure inbound results/sec: eager session, lazy session, lazy without logs."""
    manager = ConnectionManager()
    conn_id = "bench-conn"
    manager._connection_projects[conn_id] = {manager.get_connection_key("", "")}

    def open_db():
        return get_db_with_tenant_variables(test_org_id, authenticated_user_id, "")

    async def drain(messages, **handle_kwargs) -> float:
        start = time.perf_counter()
        for message in messages:
            await manager.handle_message(
                connection_id=conn_id,
                message=message,
                organization_id=None,
                **handle_kwargs,
            )
        return time.perf_counter() - start

    async def eager_drain(messages) -> float:
        """One session per message, wrapped around the call as the router did."""
        start = time.perf_counter()
        for message in messages:
            with open_db() as db:
                await manager.handle_message(
                    connection_id=conn_id,
                    message=message,
                    db=db,
                    organization_id=None,
                )
        return time.perf_counter() - start

    arms = {
        "eager session, logs at INFO": (logging.INFO, eager_drain, {}),
        "lazy session, logs at INFO": (logging.INFO, drain, {"db_factory": open_db}),
        "lazy session, logs off": (logging.WARNING, drain, {"db_factory": open_db}),
    }

    results: dict[str, float] = {}
    for label, (level, run, kwargs) in arms.items():
        counter = _CountingLogger()
        with _production_logging(level):
            with patch.object(test_result_handler, "_log_test_result", counter):
                results[label] = await run(_messages(MESSAGE_COUNT), **kwargs)
        assert counter.calls == MESSAGE_COUNT, f"{label} processed {counter.calls} messages"

    with capsys.disabled():
        print(f"\ninbound throughput over {MESSAGE_COUNT} test_result messages")
        for label, elapsed in results.items():
            print(f"  {label:<30} {MESSAGE_COUNT / elapsed:>10,.0f} results/sec")

    eager = MESSAGE_COUNT / results["eager session, logs at INFO"]
    lazy = MESSAGE_COUNT / results["lazy session, logs at INFO"]
    assert lazy > eager * 2, f"expected a large win, got {lazy:,.0f} vs {eager:,.0f} results/sec"

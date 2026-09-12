"""Request-path benchmarks: per-request overhead and event-loop stall under load.

Scenario ``request_overhead``: statements and pool checkouts a single
authenticated list request costs, before and after the handler's own work.

Scenario ``loop_stall``: N concurrent list requests while a heartbeat measures
how late the loop fires and while ``/health`` is timed from the same loop. A
sync DB call in an async dependency shows up as p99 loop lag and as health
latency that grows with N.
"""

from __future__ import annotations

import asyncio
import os
import statistics
import time

import pytest

from tests.benchmarks.backend.support import (
    ConnectionSampler,
    EngineCounter,
    LoopMonitor,
    app_client,
    percentiles,
    timed_get,
)

LIST_URL = "/test_sets/?limit=10"
CONCURRENCY_LEVELS = [int(x) for x in os.environ.get("BENCH_CONCURRENCY", "1,10,50").split(",")]
REPEATS = 20


@pytest.mark.asyncio
async def test_request_overhead(bench_auth, results):
    _org, _user, token = bench_auth
    counter = EngineCounter()
    latencies = []
    per_request = []

    async with app_client(token) as client:
        # Warm caches (permission cache, rbac_active, lazy imports) so the
        # steady-state request is what gets measured.
        for _ in range(3):
            await client.get(LIST_URL)

        with counter.active():
            for _ in range(REPEATS):
                counter.reset()
                ms, status = await timed_get(client, LIST_URL)
                assert status == 200, status
                latencies.append(ms)
                per_request.append((counter.statements, counter.checkouts))

    results["scenarios"]["request_overhead"] = {
        "url": LIST_URL,
        "statements_per_request": statistics.median(s for s, _ in per_request),
        "checkouts_per_request": statistics.median(c for _, c in per_request),
        "latency_ms": percentiles(latencies),
    }


async def _probe_health(client, stop: asyncio.Event, latencies: list[float]) -> None:
    """Time ``/health`` from the loop under test, at kubelet-like cadence minus the seconds."""
    while not stop.is_set():
        ms, status = await timed_get(client, "/health")
        latencies.append(ms)
        assert status == 200
        await asyncio.sleep(0.02)


@pytest.mark.asyncio
async def test_loop_stall_under_concurrency(bench_auth, results):
    _org, _user, token = bench_auth
    sweep = {}

    async with app_client(token) as client:
        await client.get(LIST_URL)

        for n in CONCURRENCY_LEVELS:
            monitor = LoopMonitor()
            sampler = ConnectionSampler()
            health_latencies: list[float] = []
            stop = asyncio.Event()

            async with monitor.active(), sampler.active():
                prober = asyncio.create_task(_probe_health(client, stop, health_latencies))
                start = time.perf_counter()
                outcomes = await asyncio.gather(*(timed_get(client, LIST_URL) for _ in range(n)))
                wall_ms = (time.perf_counter() - start) * 1000
                stop.set()
                await prober

            statuses = [s for _, s in outcomes]
            assert all(s == 200 for s in statuses), statuses
            sweep[str(n)] = {
                "wall_ms": wall_ms,
                "requests_per_s": n / (wall_ms / 1000) if wall_ms else 0,
                "request_latency_ms": percentiles([ms for ms, _ in outcomes]),
                "loop_lag_ms": monitor.summary(),
                "health_latency_ms": percentiles(health_latencies),
                "connections": sampler.summary(),
            }

    results["scenarios"]["loop_stall"] = {
        "url": LIST_URL,
        "db_latency_ms": float(os.environ.get("BENCH_DB_LATENCY_MS", "0")),
        "by_concurrency": sweep,
    }

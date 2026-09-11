"""Measurement helpers for the backend benchmarks.

Everything here observes the real engine, the real app and the real event loop.
None of the test-suite fixtures are used: they replace ``get_db`` and bind every
session to one connection, which removes exactly the pool checkouts and
round trips these benchmarks exist to count.
"""

from __future__ import annotations

import asyncio
import os
import statistics
import time
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Iterator

import httpx
from sqlalchemy import event, text

from rhesis.backend.app.database import engine

# Extra latency added to every statement, in the thread that runs it. This is
# how the harness stands in for a database that has become slow under job
# load: a sync call on the event loop blocks the loop for exactly this long.
DB_LATENCY_MS = float(os.environ.get("BENCH_DB_LATENCY_MS", "0"))


def percentiles(values: list[float]) -> dict[str, float]:
    if not values:
        return {"p50": 0.0, "p95": 0.0, "p99": 0.0, "max": 0.0}
    ordered = sorted(values)

    def pct(p: float) -> float:
        idx = min(len(ordered) - 1, int(round((p / 100) * (len(ordered) - 1))))
        return ordered[idx]

    return {
        "p50": pct(50),
        "p95": pct(95),
        "p99": pct(99),
        "max": ordered[-1],
        "mean": statistics.fmean(ordered),
    }


@dataclass
class EngineCounter:
    """Counts statements and pool checkouts on the app engine while active."""

    statements: int = 0
    checkouts: int = 0
    connects: int = 0
    sql: list[str] = field(default_factory=list)
    keep_sql: bool = False

    def reset(self) -> None:
        self.statements = 0
        self.checkouts = 0
        self.connects = 0
        self.sql.clear()

    def _on_execute(self, conn, cursor, statement, parameters, context, executemany):
        self.statements += 1
        if self.keep_sql:
            self.sql.append(statement)
        if DB_LATENCY_MS:
            time.sleep(DB_LATENCY_MS / 1000)

    def _on_checkout(self, dbapi_conn, record, proxy):
        self.checkouts += 1

    def _on_connect(self, dbapi_conn, record):
        self.connects += 1

    @contextmanager
    def active(self) -> Iterator["EngineCounter"]:
        event.listen(engine, "before_cursor_execute", self._on_execute)
        event.listen(engine, "checkout", self._on_checkout)
        event.listen(engine, "connect", self._on_connect)
        try:
            yield self
        finally:
            event.remove(engine, "before_cursor_execute", self._on_execute)
            event.remove(engine, "checkout", self._on_checkout)
            event.remove(engine, "connect", self._on_connect)


class LoopMonitor:
    """Samples event-loop lag: how late a 5ms heartbeat actually fires.

    A blocking call on the loop shows up as one late tick of that call's
    duration, so the tail (p99, max) is the number that matters, not the mean.
    """

    def __init__(self, interval: float = 0.005) -> None:
        self.interval = interval
        self.lags_ms: list[float] = []
        self._task: asyncio.Task | None = None

    async def _run(self) -> None:
        loop = asyncio.get_running_loop()
        while True:
            expected = loop.time() + self.interval
            await asyncio.sleep(self.interval)
            self.lags_ms.append(max(0.0, (loop.time() - expected) * 1000))

    @asynccontextmanager
    async def active(self) -> AsyncIterator["LoopMonitor"]:
        self.lags_ms.clear()
        self._task = asyncio.create_task(self._run())
        try:
            yield self
        finally:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    def summary(self) -> dict[str, float]:
        return percentiles(self.lags_ms)


@asynccontextmanager
async def app_client(token: str) -> AsyncIterator[httpx.AsyncClient]:
    """The real FastAPI app, in this loop, with its lifespan run.

    ``ASGITransport`` keeps the app on the caller's event loop, which is what
    lets ``LoopMonitor`` see the stalls a real uvicorn worker would suffer.
    ``TestClient`` would run the app on a separate thread and hide them.
    """
    from rhesis.backend.app.main import app

    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://bench",
            headers={"Authorization": f"Bearer {token}"},
            timeout=120.0,
        ) as client:
            yield client


async def timed_get(client: httpx.AsyncClient, url: str) -> tuple[float, int]:
    start = time.perf_counter()
    response = await client.get(url)
    return (time.perf_counter() - start) * 1000, response.status_code


class ConnectionSampler:
    """Polls ``pg_stat_activity`` on a side connection while a scenario runs."""

    def __init__(self, interval: float = 0.05) -> None:
        self.interval = interval
        self.samples: list[int] = []

    async def _run(self) -> None:
        import psycopg2

        from rhesis.backend.app.config.settings import get_database_settings

        conn = psycopg2.connect(get_database_settings().app_url)
        conn.autocommit = True
        try:
            while True:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT count(*) FROM pg_stat_activity "
                        "WHERE backend_type = 'client backend' AND pid <> pg_backend_pid()"
                    )
                    self.samples.append(cur.fetchone()[0])
                await asyncio.sleep(self.interval)
        finally:
            conn.close()

    @asynccontextmanager
    async def active(self) -> AsyncIterator["ConnectionSampler"]:
        self.samples.clear()
        task = asyncio.create_task(self._run())
        try:
            yield self
        finally:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    def summary(self) -> dict[str, Any]:
        return {"max": max(self.samples, default=0), "samples": len(self.samples)}


def explain(sql: str, params: dict[str, Any], *, org_id: str, user_id: str) -> str:
    """EXPLAIN ANALYZE ``sql`` as the app role with the tenant GUCs set."""
    with engine.connect() as conn:
        conn.execute(
            text(
                "SELECT set_config('app.current_organization', :org, true), "
                "set_config('app.current_user', :user, true), "
                "set_config('app.current_project', '', true)"
            ),
            {"org": org_id, "user": user_id},
        )
        rows = conn.execute(text(f"EXPLAIN (ANALYZE, BUFFERS) {sql}"), params).fetchall()
        conn.rollback()
    return "\n".join(row[0] for row in rows)

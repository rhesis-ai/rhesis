"""Temporary SQL timing probe for diagnosing N+1 query patterns.

Not wired into the app by default. To use it, add this single import near
the top of `main.py` (after `from rhesis.backend.app.database import ... engine`):

    from rhesis.backend.app import debug_sql_timing  # noqa: F401

Then hit the endpoint you're investigating and watch stdout. Remove the
import when done -- this is not meant to run in production.
"""

import logging
import re
import time
from collections import defaultdict

from sqlalchemy import event

from rhesis.backend.app.database import engine

logger = logging.getLogger("sql_timing")

_STATS: dict[str, list[float]] = defaultdict(list)


def _normalize(statement: str) -> str:
    """Collapse literal values so repeated N+1 queries group under one key."""
    normalized = re.sub(r"%\([a-zA-Z_0-9]+\)s", "?", statement)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized[:140]


@event.listens_for(engine, "before_cursor_execute")
def _before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    conn.info.setdefault("_query_start_times", []).append(time.perf_counter())


@event.listens_for(engine, "after_cursor_execute")
def _after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    start_times = conn.info.get("_query_start_times")
    if not start_times:
        return
    elapsed_ms = (time.perf_counter() - start_times.pop()) * 1000
    key = _normalize(statement)
    _STATS[key].append(elapsed_ms)
    print(f"{elapsed_ms:8.2f}ms | {key}")


def print_summary() -> None:
    """Call from a route/shell to see aggregate counts and total time per query shape."""
    rows = sorted(_STATS.items(), key=lambda kv: -sum(kv[1]))
    total_queries = sum(len(v) for _, v in rows)
    total_ms = sum(sum(v) for _, v in rows)
    print(f"\n=== SQL timing summary: {total_queries} queries, {total_ms:.1f}ms total ===")
    for key, durations in rows:
        print(f"  {len(durations):4d}x  {sum(durations):9.1f}ms total  | {key}")
    print("=" * 80)


def reset() -> None:
    _STATS.clear()

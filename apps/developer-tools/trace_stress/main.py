"""Super simple async stress tester for the worker's trace ingestion path.

Fires `POST /telemetry/traces` requests at a fixed rate to stress the
telemetry worker (the `post_ingest_link` Celery task). Each second we send
`REQUESTS_PER_SECOND` requests, each at `second_start + random(0, 1)` so they
are spread out within the second instead of bursting all at once.

Runs continuously until interrupted with Ctrl-C, then prints a summary.

Everything is configured via the constants below. No environment variables.

Run from this directory:
    uv run python trace_stress/main.py
"""

import asyncio
import itertools
import random
import time
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import httpx

# --- Configuration (edit these, no env vars) -------------------------------
BACKEND_URL = "http://localhost:8080"
API_KEY = "rh-local-token"
PROJECT_ID = "c12d6cda-931f-4e19-a643-67b7373875d5"

REQUESTS_PER_SECOND = 10
ENVIRONMENT = "development"
REQUEST_TIMEOUT = 10.0
# How long to run, in seconds. Set to 0 to run indefinitely (until Ctrl-C).
DURATION_SECONDS = 0
# ---------------------------------------------------------------------------

ENDPOINT = f"{BACKEND_URL.rstrip('/')}/telemetry/traces"
HEADERS = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}


def build_trace_batch() -> dict:
    """Build a minimal but valid single-span OTEL trace batch."""
    end = datetime.now(timezone.utc)
    start = end - timedelta(seconds=1)
    span = {
        "trace_id": uuid4().hex,  # 32-char hex
        "span_id": uuid4().hex[:16],  # 16-char hex
        "parent_span_id": None,
        "project_id": PROJECT_ID,
        "environment": ENVIRONMENT,
        "span_name": "ai.llm.invoke",
        "span_kind": "INTERNAL",
        "start_time": start.isoformat(),
        "end_time": end.isoformat(),
        "status_code": "OK",
        "attributes": {
            "ai.operation.type": "ai.llm.invoke",
            "ai.model.provider": "stress-test",
            "ai.model.name": "mock",
            "rhesis.conversation.input": "stress test request",
        },
    }
    return {"spans": [span]}


async def send_one(client: httpx.AsyncClient, delay: float, results: list) -> None:
    """Wait `delay` seconds, then fire one trace ingestion request."""
    await asyncio.sleep(delay)
    sent_at = time.perf_counter()
    try:
        resp = await client.post(ENDPOINT, headers=HEADERS, json=build_trace_batch())
        elapsed = time.perf_counter() - sent_at
        results.append((resp.status_code, elapsed))
    except Exception as exc:  # noqa: BLE001
        results.append((repr(exc), time.perf_counter() - sent_at))


async def main() -> None:
    run_for = f"for {DURATION_SECONDS}s" if DURATION_SECONDS > 0 else "until Ctrl-C"
    print(f"Stress testing {ENDPOINT}\n  {REQUESTS_PER_SECOND} req/s {run_for}\n")
    results: list = []
    tasks: list[asyncio.Task] = []

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        loop_start = time.perf_counter()
        try:
            for second in itertools.count():
                if DURATION_SECONDS > 0 and second >= DURATION_SECONDS:
                    break
                for _ in range(REQUESTS_PER_SECOND):
                    # Spread requests across the current second.
                    delay = (second + random.random()) - (time.perf_counter() - loop_start)
                    tasks.append(asyncio.create_task(send_one(client, max(delay, 0), results)))
                # Hold until the next second boundary before scheduling more.
                await asyncio.sleep(max((second + 1) - (time.perf_counter() - loop_start), 0))
        except (KeyboardInterrupt, asyncio.CancelledError):
            print("\nInterrupted, waiting for in-flight requests...")
        finally:
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)

    total = len(results)
    ok = sum(1 for status, _ in results if status == 200)
    latencies = sorted(elapsed for _, elapsed in results)
    avg = sum(latencies) / total if total else 0.0
    p95 = latencies[int(total * 0.95)] if total else 0.0

    print(f"\nDone: {ok}/{total} succeeded")
    print(f"  avg latency: {avg * 1000:.0f}ms   p95: {p95 * 1000:.0f}ms")

    errors = {status for status, _ in results if status != 200}
    if errors:
        print(f"  non-200 / errors: {errors}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass

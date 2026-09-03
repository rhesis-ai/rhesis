"""Per-test execution phase timing, for the verdict grid's live animation.

The Summary tab's strip animates each test through pending -> generating ->
evaluating -> resolved. Rather than scripting a sweep, it derives every cell's
colour from when those transitions actually happened, so the advancing frontier
is real: a slow test genuinely lags behind its neighbours.

Those moments are only observable from inside the worker (``on_test_phase``),
and they are only wanted while somebody is watching the run, so they live in
Redis under a TTL instead of on the ``test_result`` row. Losing them costs the
animation and nothing else -- the grid still renders from the verdicts alone.

Offsets are stored as **deciseconds since this run's own origin**, which keeps
the payload small on a large run and hands the frontend the exact unit its
clock already uses. The origin is recorded here on the first phase callback
rather than read from ``test_run.attributes["started_at"]``: that attribute is
set after this callback is built, and reading it back from a worker thread
would refresh an expired ORM object off-session. Everything downstream is
measured against the origin recorded here, so it stays self-consistent.
"""

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from enum import Enum
from typing import Dict, Optional, Tuple

from rhesis.backend.app.services.cache import RedisBackedCache
from rhesis.backend.app.services.redis_constants import RedisDatabase

logger = logging.getLogger(__name__)

_PREFIX = "trtiming:"
_ORIGIN_FIELD = "_origin"
# Long enough to outlive any run somebody is plausibly still watching.
_CACHE_TTL = 2 * 60 * 60


class TestPhase(str, Enum):
    """A test's live execution phase, as reported by on_test_phase.

    Defined here rather than in jobs/execution/ -- this module is the
    service-layer owner of the concept, and jobs/ depends on app/services/,
    never the reverse (see apps/backend/AGENTS.md's "Jobs layout"). Every
    on_test_phase call site across both execution paths (sequential.py,
    batch/runner.py, executors/runners.py) imports this rather than passing
    a bare string, so a typo at a call site is a type error, not a silently
    dropped phase transition -- the exact failure mode that shipped the
    test_status 'G'/'E' mismatch bug earlier.
    """

    GENERATING = "generating"
    EVALUATING = "evaluating"
    DONE = "done"


# TestPhase -> the field suffix each phase lands in.
# EVALUATING marks the end of generation, DONE the end of evaluation.
PHASE_FIELDS: Dict[TestPhase, str] = {
    TestPhase.GENERATING: "s",
    TestPhase.EVALUATING: "g",
    TestPhase.DONE: "r",
}


class TestTiming:
    """One test's phase offsets, in deciseconds since the run origin."""

    __slots__ = ("started_ds", "generated_ds", "resolved_ds")

    def __init__(
        self,
        started_ds: Optional[int] = None,
        generated_ds: Optional[int] = None,
        resolved_ds: Optional[int] = None,
    ) -> None:
        self.started_ds = started_ds
        self.generated_ds = generated_ds
        self.resolved_ds = resolved_ds


class TestRunTimingCache(RedisBackedCache):
    """Phase offsets per test, keyed by test run. Sync, to match its callers."""

    def __init__(self) -> None:
        super().__init__(
            redis_db=RedisDatabase.TEST_RUN_TIMING,
            cache_name="test-run-timing",
            ttl=_CACHE_TTL,
        )
        # Origins are immutable once set, so memoising them per process turns
        # every phase callback after the first into a single write.
        self._origins: Dict[str, float] = {}
        self._origin_lock = threading.Lock()

    def _key(self, test_run_id: str) -> str:
        return f"{_PREFIX}{test_run_id}"

    def ensure_origin(self, test_run_id: str) -> float:
        """Return this run's t=0 as an epoch float, recording it if unset.

        Idempotent across workers: the first writer wins and everyone else
        reads that value back, so offsets from different processes share one
        origin.
        """
        run_id = str(test_run_id)
        with self._origin_lock:
            cached = self._origins.get(run_id)
        if cached is not None:
            return cached

        key = self._key(run_id)
        now = time.time()
        origin = now

        if self._using_redis:
            try:
                pipe = self._redis.pipeline()
                pipe.hsetnx(key, _ORIGIN_FIELD, repr(now))
                pipe.hget(key, _ORIGIN_FIELD)
                pipe.expire(key, _CACHE_TTL)
                results = pipe.execute()
                stored = results[1]
                if stored:
                    origin = float(stored)
            except Exception as exc:
                logger.warning(f"test-run-timing: origin write failed: {exc}")
        else:
            with self._lock:
                bucket = self._memory.get(key)
                if not isinstance(bucket, dict):
                    bucket = {}
                    self._memory[key] = bucket
                stored = bucket.get(_ORIGIN_FIELD)
                if stored is None:
                    bucket[_ORIGIN_FIELD] = repr(now)
                else:
                    origin = float(stored)
                self._memory_timestamps[key] = time.monotonic()

        with self._origin_lock:
            self._origins[run_id] = origin
        return origin

    def record_phase(self, test_run_id: str, test_id: str, phase: TestPhase, origin: float) -> None:
        """Stamp one test's transition into `phase`, relative to `origin`."""
        field_suffix = PHASE_FIELDS.get(phase)
        if field_suffix is None:
            return
        offset_ds = max(0, int(round((time.time() - origin) * 10)))
        self._hset(
            self._key(str(test_run_id)),
            f"{test_id}:{field_suffix}",
            str(offset_ds),
            ttl=_CACHE_TTL,
        )

    def record_phase_now(self, test_run_id: str, test_id: str, phase: TestPhase) -> None:
        """Resolve the run's origin and record one phase transition.

        Combines ensure_origin + record_phase behind a single call so the
        caller doesn't need to memoise the origin itself -- this class
        already does, in `_origins`.
        """
        origin = self.ensure_origin(test_run_id)
        self.record_phase(test_run_id, test_id, phase, origin)

    def get_run_timing(self, test_run_id: str) -> Tuple[Optional[float], Dict[str, TestTiming]]:
        """Return (origin epoch, {test_id: TestTiming}) for a run.

        Returns (None, {}) when nothing was recorded -- an old run whose TTL
        lapsed, or one that predates this tracking. Callers render the grid in
        its settled state rather than treating that as an error.
        """
        raw = self._hgetall(self._key(str(test_run_id)))
        if not raw:
            return None, {}

        origin: Optional[float] = None
        timings: Dict[str, TestTiming] = {}

        for field, value in raw.items():
            if field == _ORIGIN_FIELD:
                try:
                    origin = float(value)
                except (TypeError, ValueError):
                    logger.debug("test-run-timing: unparseable origin %r", value)
                continue

            test_id, _, suffix = field.rpartition(":")
            if not test_id:
                continue
            try:
                offset_ds = int(value)
            except (TypeError, ValueError):
                continue

            entry = timings.get(test_id)
            if entry is None:
                entry = TestTiming()
                timings[test_id] = entry
            if suffix == "s":
                entry.started_ds = offset_ds
            elif suffix == "g":
                entry.generated_ds = offset_ds
            elif suffix == "r":
                entry.resolved_ds = offset_ds

        return origin, timings


_cache = TestRunTimingCache()

# Batch execution runs many tests concurrently as coroutines on one shared
# event loop; a synchronous Redis round-trip called inline from any of them
# would block every other in-flight test for its duration. record_phase_async
# below offloads the write to this pool instead -- the same reason
# TestRunProgressed's own publish is deferred to a thread by TestRunSink
# rather than issued inline. Sequential execution has no event loop running
# between tests either, so this can't lean on asyncio primitives; plain OS
# threads work unchanged in both call sites.
_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="trtiming")


def get_test_run_timing_cache() -> TestRunTimingCache:
    """The process-wide timing cache. Connects on first use, not on import."""
    _cache.initialize()
    return _cache


def _record_phase_now(test_run_id: str, test_id: str, phase: TestPhase) -> None:
    get_test_run_timing_cache().record_phase_now(test_run_id, test_id, phase)


def record_phase_async(test_run_id: str, test_id: str, phase: TestPhase) -> None:
    """Fire-and-forget: record a phase transition without blocking the caller.

    get_test_run_timing_cache() is resolved *inside* the submitted task, not
    before -- on first use it connects to Redis, and resolving it here would
    do that blocking handshake on the caller's own thread, defeating the
    entire reason for dispatching this off-thread in the first place.

    Never raises -- a scheduling failure degrades the animation, not the run.
    """
    try:
        _executor.submit(_record_phase_now, test_run_id, test_id, phase)
    except Exception:
        logger.debug("test run timing schedule failed", exc_info=True)

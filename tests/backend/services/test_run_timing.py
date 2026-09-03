"""Unit tests for the verdict grid's per-test phase timing.

These offsets drive the Summary strip's animation, so the properties that
matter are: one stable origin per run (offsets from different callbacks must
share a zero point), phases landing in the right slot, and partial timing
surviving intact -- a test can be cut off mid-run, and a Redis hiccup can
drop an individual phase write.
"""

import time
from unittest.mock import patch

import pytest

from rhesis.backend.app.services.test_run import _TIMING_MAX_TESTS, _build_timing_columns
from rhesis.backend.app.services.test_run_timing import (
    PHASE_FIELDS,
    TestPhase,
    TestRunTimingCache,
    record_phase_async,
)


def _memory_cache() -> TestRunTimingCache:
    """A cache pinned to its in-memory fallback (no Redis in unit tests)."""
    with patch("redis.Redis.from_url", side_effect=ConnectionError("unavailable")):
        cache = TestRunTimingCache()
        cache.initialize()
    assert cache._using_redis is False
    return cache


@pytest.mark.unit
class TestOrigin:
    def test_origin_is_stable_across_calls(self):
        cache = _memory_cache()
        first = cache.ensure_origin("run-1")
        assert cache.ensure_origin("run-1") == first

    def test_origin_survives_the_process_memo_being_dropped(self):
        # Two workers on one run must agree on t=0, so the stored value wins
        # over a fresh local timestamp.
        cache = _memory_cache()
        first = cache.ensure_origin("run-1")
        cache._origins.clear()
        assert cache.ensure_origin("run-1") == first

    def test_separate_runs_get_separate_origins(self):
        cache = _memory_cache()
        cache.ensure_origin("run-1")
        cache.ensure_origin("run-2")
        assert cache._origins["run-1"] != cache._origins["run-2"]


@pytest.mark.unit
class TestRecordPhase:
    def test_phases_land_in_their_own_slots(self):
        cache = _memory_cache()
        origin = cache.ensure_origin("run-1")

        cache.record_phase("run-1", "t1", TestPhase.GENERATING, origin - 1.0)
        cache.record_phase("run-1", "t1", TestPhase.EVALUATING, origin - 3.0)
        cache.record_phase("run-1", "t1", TestPhase.DONE, origin - 5.2)

        _, timings = cache.get_run_timing("run-1")
        assert (timings["t1"].started_ds, timings["t1"].generated_ds) == (10, 30)
        assert timings["t1"].resolved_ds == 52

    def test_partial_timing_leaves_later_phases_none(self):
        # A dropped write (Redis hiccup) shouldn't corrupt the phases that
        # did land -- both execution paths report all three phases now, but
        # any individual one can still go missing.
        cache = _memory_cache()
        origin = cache.ensure_origin("run-1")

        cache.record_phase("run-1", "t1", TestPhase.GENERATING, origin - 2.0)
        cache.record_phase("run-1", "t1", TestPhase.DONE, origin - 6.0)

        _, timings = cache.get_run_timing("run-1")
        assert timings["t1"].started_ds == 20
        assert timings["t1"].generated_ds is None
        assert timings["t1"].resolved_ds == 60

    def test_unknown_phase_is_ignored(self):
        cache = _memory_cache()
        origin = cache.ensure_origin("run-1")
        cache.record_phase("run-1", "t1", "not-a-phase", origin)

        _, timings = cache.get_run_timing("run-1")
        assert timings == {}

    def test_clock_skew_never_yields_a_negative_offset(self):
        # An origin in the future would otherwise rewind the animation.
        cache = _memory_cache()
        origin = cache.ensure_origin("run-1")
        cache.record_phase("run-1", "t1", TestPhase.GENERATING, origin + 30.0)

        _, timings = cache.get_run_timing("run-1")
        assert timings["t1"].started_ds == 0

    def test_phase_vocabulary_matches_the_worker_callback(self):
        # on_test_phase emits exactly these three; a rename on either side
        # would silently stop recording.
        assert set(PHASE_FIELDS) == {TestPhase.GENERATING, TestPhase.EVALUATING, TestPhase.DONE}


@pytest.mark.unit
class TestRecordPhaseNow:
    def test_resolves_origin_and_records_in_one_call(self):
        cache = _memory_cache()
        cache.record_phase_now("run-1", "t1", TestPhase.GENERATING)

        origin, timings = cache.get_run_timing("run-1")
        assert origin is not None
        assert timings["t1"].started_ds == 0

    def test_reuses_the_memoised_origin_across_calls(self):
        cache = _memory_cache()
        cache.record_phase_now("run-1", "t1", TestPhase.GENERATING)
        origin_after_first = cache._origins["run-1"]

        cache.record_phase_now("run-1", "t2", TestPhase.GENERATING)
        assert cache._origins["run-1"] == origin_after_first


@pytest.mark.unit
class TestRecordPhaseAsync:
    """record_phase_async must never block its caller with a Redis round-trip.

    Batch execution runs many tests concurrently as coroutines on one shared
    event loop; an inline synchronous write here would serialize them.
    """

    def test_returns_without_waiting_for_the_cache_to_connect(self):
        # get_test_run_timing_cache() connects to Redis on first use; that
        # handshake must happen inside the submitted task, never on the
        # caller's own thread, or the very first phase transition of every
        # run would pay that latency inline.
        with patch(
            "rhesis.backend.app.services.test_run_timing.get_test_run_timing_cache"
        ) as get_cache:

            def slow_connect():
                time.sleep(0.2)
                return _memory_cache()

            get_cache.side_effect = slow_connect

            started = time.monotonic()
            record_phase_async("run-1", "t1", TestPhase.GENERATING)
            elapsed = time.monotonic() - started

        assert elapsed < 0.05, (
            "record_phase_async blocked the caller instead of dispatching off-thread"
        )

    def test_the_dispatched_write_eventually_lands(self):
        cache = _memory_cache()
        with patch(
            "rhesis.backend.app.services.test_run_timing.get_test_run_timing_cache",
            return_value=cache,
        ):
            record_phase_async("run-1", "t1", TestPhase.GENERATING)

            deadline = time.monotonic() + 1.0
            timings = {}
            while time.monotonic() < deadline:
                _, timings = cache.get_run_timing("run-1")
                if "t1" in timings:
                    break
                time.sleep(0.01)

        assert timings.get("t1") is not None
        assert timings["t1"].started_ds is not None

    def test_a_scheduling_failure_is_swallowed(self):
        with patch(
            "rhesis.backend.app.services.test_run_timing.get_test_run_timing_cache",
            side_effect=RuntimeError("cache unavailable"),
        ):
            record_phase_async("run-1", "t1", TestPhase.GENERATING)  # must not raise


@pytest.mark.unit
class TestGetRunTiming:
    def test_unknown_run_returns_empty(self):
        cache = _memory_cache()
        assert cache.get_run_timing("never-ran") == (None, {})

    def test_origin_round_trips(self):
        cache = _memory_cache()
        origin = cache.ensure_origin("run-1")
        cache.record_phase("run-1", "t1", TestPhase.GENERATING, origin)

        stored_origin, _ = cache.get_run_timing("run-1")
        assert stored_origin == pytest.approx(origin, abs=0.01)

    def test_several_tests_are_kept_apart(self):
        cache = _memory_cache()
        origin = cache.ensure_origin("run-1")
        cache.record_phase("run-1", "t1", TestPhase.GENERATING, origin - 1.0)
        cache.record_phase("run-1", "t2", TestPhase.GENERATING, origin - 4.0)

        _, timings = cache.get_run_timing("run-1")
        assert timings["t1"].started_ds == 10
        assert timings["t2"].started_ds == 40

    def test_uuid_test_ids_survive_the_field_split(self):
        # Field names are "{test_id}:{suffix}" and a UUID has no colons, but
        # the parse must rsplit regardless so an id containing one can't
        # shift the phase suffix.
        cache = _memory_cache()
        origin = cache.ensure_origin("run-1")
        test_id = "3f2504e0-4f89-11d3-9a0c-0305e82c3301"
        cache.record_phase("run-1", test_id, TestPhase.EVALUATING, origin - 1.5)

        _, timings = cache.get_run_timing("run-1")
        assert timings[test_id].generated_ds == 15

    def test_corrupt_values_are_skipped_not_raised(self):
        cache = _memory_cache()
        origin = cache.ensure_origin("run-1")
        cache.record_phase("run-1", "t1", TestPhase.GENERATING, origin - 1.0)
        cache._hset(cache._key("run-1"), "t2:s", "not-a-number")

        _, timings = cache.get_run_timing("run-1")
        assert timings["t1"].started_ds == 10
        assert "t2" not in timings


@pytest.mark.unit
class TestBuildTimingColumns:
    """The verdict matrix's timing columns must line up with test_order.

    A misalignment here would animate the wrong tests without failing
    anything, so ordering is asserted explicitly rather than by count.
    """

    def _columns(self, cache, test_order, run_id="run-1"):
        with patch(
            "rhesis.backend.app.services.test_run_timing.get_test_run_timing_cache",
            return_value=cache,
        ):
            return _build_timing_columns(run_id, test_order)

    def test_columns_follow_test_order_not_insertion_order(self):
        cache = _memory_cache()
        origin = cache.ensure_origin("run-1")
        cache.record_phase("run-1", "t2", TestPhase.GENERATING, origin - 2.0)
        cache.record_phase("run-1", "t1", TestPhase.GENERATING, origin - 1.0)

        started, _, _, _ = self._columns(cache, ["t1", "t2"])
        assert started == [10, 20]

    def test_tests_without_timing_become_none_holes(self):
        cache = _memory_cache()
        origin = cache.ensure_origin("run-1")
        cache.record_phase("run-1", "t1", TestPhase.GENERATING, origin - 1.0)
        cache.record_phase("run-1", "t3", TestPhase.GENERATING, origin - 3.0)

        started, _, _, _ = self._columns(cache, ["t1", "t2", "t3"])
        assert started == [10, None, 30]

    def test_all_phases_are_returned_together(self):
        cache = _memory_cache()
        origin = cache.ensure_origin("run-1")
        cache.record_phase("run-1", "t1", TestPhase.GENERATING, origin - 1.0)
        cache.record_phase("run-1", "t1", TestPhase.EVALUATING, origin - 2.0)
        cache.record_phase("run-1", "t1", TestPhase.DONE, origin - 4.0)

        started, generated, resolved, _ = self._columns(cache, ["t1"])
        assert (started, generated, resolved) == ([10], [20], [40])

    def test_elapsed_is_reported_against_the_stored_origin(self):
        cache = _memory_cache()
        origin = cache.ensure_origin("run-1")
        cache.record_phase("run-1", "t1", TestPhase.GENERATING, origin)

        *_, elapsed_ds = self._columns(cache, ["t1"])
        assert elapsed_ds is not None and elapsed_ds >= 0

    def test_run_with_no_recorded_timing_yields_all_none(self):
        # An old run whose TTL lapsed: the grid renders settled instead of
        # erroring.
        cache = _memory_cache()
        assert self._columns(cache, ["t1", "t2"]) == (None, None, None, None)

    def test_elapsed_is_reported_before_the_first_phase_lands(self):
        # A run just picked up by a worker has an origin but no phases yet;
        # elapsed still flows so the client's clock starts reconciling.
        cache = _memory_cache()
        cache.ensure_origin("run-1")

        started, generated, resolved, elapsed_ds = self._columns(cache, ["t1"])
        assert (started, generated, resolved) == (None, None, None)
        assert elapsed_ds is not None and elapsed_ds >= 0

    def test_empty_test_order_yields_all_none(self):
        cache = _memory_cache()
        cache.ensure_origin("run-1")
        assert self._columns(cache, []) == (None, None, None, None)

    def test_large_runs_skip_timing_entirely(self):
        cache = _memory_cache()
        origin = cache.ensure_origin("run-1")
        cache.record_phase("run-1", "t0", TestPhase.GENERATING, origin)

        oversized = [f"t{i}" for i in range(_TIMING_MAX_TESTS + 1)]
        assert self._columns(cache, oversized) == (None, None, None, None)

    def test_cache_failure_degrades_instead_of_raising(self):
        cache = _memory_cache()
        with patch.object(cache, "get_run_timing", side_effect=RuntimeError("redis down")):
            assert self._columns(cache, ["t1"]) == (None, None, None, None)

"""Unit tests for the stale-run rule.

A narrow pure function over a run summary and a clock, tested directly for the
same reason ``material_change`` is: the branches are the point, and driving each
one through a whole run would be slow and would hide what is being asserted.

The rule exists to stop a ``running`` claim nobody is behind from refusing every
later run forever — a crashed worker, or a dispatch that never reached one.

Run with: python -m pytest tests/backend/services/metric_tuning/test_staleness.py -v
"""

from datetime import datetime, timedelta, timezone

import pytest

from rhesis.backend.app.schemas.metric_tuning_metadata import (
    MetricTuningRunSummary,
    TuningRunStatus,
)
from rhesis.backend.app.services.metric_tuning.staleness import (
    STALE_RUN_AFTER,
    STALE_RUN_MESSAGE,
    abandoned,
    parse_timestamp,
    run_is_stale,
)

NOW = datetime(2026, 8, 20, 12, 0, tzinfo=timezone.utc)


def _running(**fields) -> MetricTuningRunSummary:
    return MetricTuningRunSummary(status=TuningRunStatus.RUNNING, **fields)


def _iso(delta: timedelta) -> str:
    return (NOW - delta).isoformat()


@pytest.mark.unit
class TestRunIsStale:
    """Only a claim that has stopped advancing is stale."""

    def test_a_run_that_just_started_is_not_stale(self):
        assert not run_is_stale(_running(started_at=_iso(timedelta(seconds=1))), NOW)

    def test_a_run_advancing_within_the_window_is_not_stale(self):
        """The heartbeat is per case, so a long set keeps renewing it."""
        summary = _running(
            started_at=_iso(timedelta(hours=4)),
            progressed_at=_iso(STALE_RUN_AFTER - timedelta(minutes=1)),
        )

        assert not run_is_stale(summary, NOW)

    def test_a_run_that_stopped_advancing_is_stale(self):
        summary = _running(
            started_at=_iso(timedelta(hours=4)),
            progressed_at=_iso(STALE_RUN_AFTER + timedelta(minutes=1)),
        )

        assert run_is_stale(summary, NOW)

    def test_exactly_on_the_window_is_not_yet_stale(self):
        """The boundary belongs to the run that is still going."""
        assert not run_is_stale(_running(progressed_at=_iso(STALE_RUN_AFTER)), NOW)

    def test_the_heartbeat_wins_over_the_start(self):
        """A run started long ago but still working is alive."""
        summary = _running(
            started_at=_iso(timedelta(days=2)),
            progressed_at=_iso(timedelta(minutes=1)),
        )

        assert not run_is_stale(summary, NOW)

    def test_a_claim_written_before_the_heartbeat_existed_falls_back_to_started_at(self):
        """Nothing migrates the summary, so an old claim is read on `started_at`."""
        assert run_is_stale(_running(started_at=_iso(STALE_RUN_AFTER * 2)), NOW)
        assert not run_is_stale(_running(started_at=_iso(timedelta(minutes=1))), NOW)

    def test_a_claim_with_no_timestamps_at_all_is_stale(self):
        """It cannot be shown to be alive, and holding the metric on it is the wedge."""
        assert run_is_stale(_running(), NOW)

    def test_an_unparseable_timestamp_is_stale(self):
        assert run_is_stale(_running(progressed_at="whenever"), NOW)

    def test_a_naive_timestamp_is_read_as_utc_rather_than_crashing(self):
        naive = NOW.replace(tzinfo=None) - timedelta(minutes=1)
        assert not run_is_stale(_running(progressed_at=naive.isoformat()), NOW)

    @pytest.mark.parametrize(
        "status",
        [TuningRunStatus.NEVER_RUN, TuningRunStatus.COMPLETED, TuningRunStatus.FAILED],
    )
    def test_only_a_running_claim_can_be_stale(self, status):
        """A finished run is not blocking anything, however old it is."""
        summary = MetricTuningRunSummary(status=status, progressed_at=_iso(timedelta(days=30)))

        assert not run_is_stale(summary, NOW)

    def test_the_clock_defaults_to_now(self):
        assert run_is_stale(_running(progressed_at=_iso(timedelta(days=1))))


@pytest.mark.unit
class TestAbandoned:
    """How a stale claim is presented to whoever asked about the run."""

    def test_it_reads_as_failed_and_says_why(self):
        stale = abandoned(_running(started_at=_iso(timedelta(hours=1)), total_cases=5))

        assert stale.status == TuningRunStatus.FAILED
        assert stale.error == STALE_RUN_MESSAGE

    def test_it_keeps_the_counts_the_run_did_reach(self):
        stale = abandoned(_running(total_cases=5, completed_cases=2, errored_cases=1))

        assert (stale.total_cases, stale.completed_cases, stale.errored_cases) == (5, 2, 1)

    def test_it_never_completed_so_it_has_no_completion_time(self):
        assert abandoned(_running(started_at=_iso(timedelta(hours=1)))).completed_at is None

    def test_the_stored_summary_is_left_alone(self):
        """Reading a run must not rewrite one — the copy is the whole point."""
        summary = _running(started_at=_iso(timedelta(hours=1)))

        abandoned(summary)

        assert summary.status == TuningRunStatus.RUNNING
        assert summary.error is None


@pytest.mark.unit
class TestParseTimestamp:
    def test_none_and_empty_are_not_timestamps(self):
        assert parse_timestamp(None) is None
        assert parse_timestamp("") is None

    def test_garbage_is_not_a_timestamp(self):
        assert parse_timestamp("last tuesday") is None

    def test_an_aware_timestamp_keeps_its_zone(self):
        assert parse_timestamp(NOW.isoformat()) == NOW

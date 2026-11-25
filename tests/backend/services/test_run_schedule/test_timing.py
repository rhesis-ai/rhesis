"""When a test run schedule runs: cron in the schedule's time zone, DST, ends, exceptions."""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from rhesis.backend.app.schemas.test_run_schedule import ScheduleException, ScheduleSpecIn
from rhesis.backend.app.services.test_run_schedule.timing import (
    ScheduleTiming,
    compute_next_run,
    describe_schedule,
    is_overdue,
    min_gap,
    occurrences,
    prune_exceptions,
)

pytestmark = pytest.mark.unit

BERLIN = ZoneInfo("Europe/Berlin")
UTC = timezone.utc


def berlin(*args) -> datetime:
    return datetime(*args, tzinfo=BERLIN).astimezone(UTC)


def utc(*args) -> datetime:
    return datetime(*args, tzinfo=UTC)


def cron(expression: str, zone: str = "Europe/Berlin", ends_at=None) -> ScheduleTiming:
    return ScheduleTiming(cron=expression, run_at=None, timezone=zone, ends_at=ends_at)


def times(timing, start, end, exceptions=(), limit=None):
    return [o.at for o in occurrences(timing, start, end, exceptions, limit)]


class TestOccurrences:
    def test_weekdays_skip_the_weekend(self):
        # Mon 23 Nov 2026 to Mon 30 Nov 2026
        result = times(cron("0 9 * * 1-5"), berlin(2026, 11, 23), berlin(2026, 11, 30))
        assert result == [berlin(2026, 11, day, 9) for day in (23, 24, 25, 26, 27)]

    def test_hourly(self):
        result = times(cron("0 * * * *"), berlin(2026, 11, 23, 9), berlin(2026, 11, 23, 12))
        assert result == [berlin(2026, 11, 23, hour) for hour in (9, 10, 11)]

    def test_daily_keeps_local_time_across_dst(self):
        result = times(cron("0 9 * * *"), berlin(2026, 3, 28), berlin(2026, 3, 31))
        assert result == [berlin(2026, 3, day, 9) for day in (28, 29, 30)]
        assert [t.hour for t in result] == [8, 7, 7]  # UTC hour moves, local stays 09:00

    def test_weekly_on_monday_and_thursday(self):
        result = times(cron("30 7 * * 1,4"), berlin(2026, 11, 23), berlin(2026, 12, 7))
        assert result == [berlin(2026, 11, d, 7, 30) for d in (23, 26)] + [
            berlin(2026, 11, 30, 7, 30),
            berlin(2026, 12, 3, 7, 30),
        ]

    def test_monthly_on_the_first(self):
        result = times(cron("0 9 1 * *"), berlin(2026, 11, 2), berlin(2027, 2, 2))
        assert result == [berlin(2026, 12, 1, 9), berlin(2027, 1, 1, 9), berlin(2027, 2, 1, 9)]

    def test_monthly_on_the_last_day(self):
        result = times(cron("0 9 L * *"), berlin(2027, 1, 1), berlin(2027, 4, 1))
        assert result == [berlin(2027, 1, 31, 9), berlin(2027, 2, 28, 9), berlin(2027, 3, 31, 9)]

    def test_monthly_on_the_31st_skips_short_months(self):
        result = times(cron("0 9 31 * *"), berlin(2027, 1, 1), berlin(2027, 6, 1))
        assert result == [berlin(2027, m, 31, 9) for m in (1, 3, 5)]

    def test_run_once(self):
        at = utc(2026, 12, 1, 12)
        timing = ScheduleTiming(cron=None, run_at=at, timezone="UTC")
        assert times(timing, utc(2026, 11, 1), utc(2027, 1, 1)) == [at]
        assert times(timing, utc(2026, 12, 2), utc(2027, 1, 1)) == []


class TestDaylightSaving:
    def test_a_time_missing_on_the_spring_day_runs_at_the_first_valid_time(self):
        # 29 Mar 2026: Berlin clocks jump from 02:00 to 03:00.
        result = times(cron("30 2 * * *"), berlin(2026, 3, 28), berlin(2026, 3, 31))
        assert result == [
            berlin(2026, 3, 28, 2, 30),
            berlin(2026, 3, 29, 3),
            berlin(2026, 3, 30, 2, 30),
        ]

    def test_a_time_that_happens_twice_on_the_autumn_day_runs_once(self):
        # 25 Oct 2026: Berlin clocks go back from 03:00 to 02:00.
        result = times(cron("30 2 * * *"), berlin(2026, 10, 24), berlin(2026, 10, 27))
        assert len(result) == 3
        assert result[1] == datetime(2026, 10, 25, 2, 30, tzinfo=BERLIN).astimezone(UTC)
        assert result[1] == utc(2026, 10, 25, 0, 30)  # the first 02:30, still summer time

    def test_next_run_after_the_first_repeated_time_skips_the_second(self):
        first = utc(2026, 10, 25, 0, 30)
        nxt = compute_next_run(cron("30 2 * * *"), first)
        assert nxt.at == berlin(2026, 10, 26, 2, 30)


class TestEnds:
    def test_ends_at_stops_the_sequence(self):
        timing = cron("0 9 * * *", ends_at=berlin(2026, 11, 25, 12))
        result = times(timing, berlin(2026, 11, 23), berlin(2026, 12, 1))
        assert result == [berlin(2026, 11, d, 9) for d in (23, 24, 25)]
        assert compute_next_run(timing, berlin(2026, 11, 25, 9)) is None

    def test_limit_caps_the_runs_left_under_max_runs(self):
        result = times(cron("0 9 * * *"), berlin(2026, 11, 23), berlin(2026, 12, 1), limit=2)
        assert result == [berlin(2026, 11, 23, 9), berlin(2026, 11, 24, 9)]


class TestExceptions:
    WEEKDAYS = cron("0 9 * * 1-5")

    def test_skip_removes_the_run(self):
        skip = [{"occurrence": berlin(2026, 11, 24, 9).isoformat(), "skip": True}]
        result = times(self.WEEKDAYS, berlin(2026, 11, 23), berlin(2026, 11, 26), skip)
        assert result == [berlin(2026, 11, 23, 9), berlin(2026, 11, 25, 9)]

    def test_move_relocates_and_keeps_the_original(self):
        moved_to = berlin(2026, 11, 24, 15)
        move = [{"occurrence": berlin(2026, 11, 24, 9).isoformat(), "run_at": moved_to.isoformat()}]
        result = occurrences(self.WEEKDAYS, berlin(2026, 11, 24), berlin(2026, 11, 25), move)
        assert len(result) == 1
        assert result[0].at == moved_to
        assert result[0].original == berlin(2026, 11, 24, 9)
        assert result[0].changed

    def test_a_run_moved_into_the_window_from_outside_shows(self):
        move = [
            {
                "occurrence": berlin(2026, 11, 23, 9).isoformat(),
                "run_at": berlin(2026, 11, 28, 10).isoformat(),
            }
        ]
        result = times(self.WEEKDAYS, berlin(2026, 11, 28), berlin(2026, 11, 29), move)
        assert result == [berlin(2026, 11, 28, 10)]

    def test_a_move_to_a_time_that_is_not_a_run_is_ignored(self):
        move = [
            {
                "occurrence": berlin(2026, 11, 28, 9).isoformat(),
                "run_at": berlin(2026, 11, 28, 10).isoformat(),
            }
        ]
        assert times(self.WEEKDAYS, berlin(2026, 11, 28), berlin(2026, 11, 29), move) == []

    def test_next_run_is_the_earliest_of_regular_and_moved(self):
        move = [
            {
                "occurrence": berlin(2026, 11, 24, 9).isoformat(),
                "run_at": berlin(2026, 11, 23, 15).isoformat(),
            }
        ]
        nxt = compute_next_run(self.WEEKDAYS, berlin(2026, 11, 23, 9), move)
        assert nxt.at == berlin(2026, 11, 23, 15)
        assert nxt.original == berlin(2026, 11, 24, 9)
        after = compute_next_run(self.WEEKDAYS, nxt.at, move)
        assert after.at == berlin(2026, 11, 25, 9)

    def test_next_run_passes_over_a_moved_later_run(self):
        move = [
            {
                "occurrence": berlin(2026, 11, 24, 9).isoformat(),
                "run_at": berlin(2026, 11, 26, 18).isoformat(),
            }
        ]
        nxt = compute_next_run(self.WEEKDAYS, berlin(2026, 11, 23, 9), move)
        assert nxt.at == berlin(2026, 11, 25, 9)

    def test_pruning_drops_past_entries(self):
        entries = [
            {"occurrence": berlin(2026, 11, 23, 9).isoformat(), "skip": True},
            {
                "occurrence": berlin(2026, 11, 23, 9, 30).isoformat(),
                "run_at": berlin(2026, 11, 27, 9).isoformat(),
            },
            {"occurrence": berlin(2026, 11, 26, 9).isoformat(), "skip": True},
        ]
        kept = prune_exceptions(entries, berlin(2026, 11, 24, 9))
        assert kept == entries[1:]
        assert prune_exceptions(entries, None) == entries


class TestMinGap:
    def test_every_minute_is_one_minute(self):
        assert min_gap(cron("* * * * *")) == timedelta(minutes=1)

    def test_two_times_close_together_in_a_day(self):
        assert min_gap(cron("0,30 9 * * *")) == timedelta(minutes=30)

    def test_run_once_has_no_gap(self):
        assert min_gap(ScheduleTiming(None, utc(2027, 1, 1), "UTC")) == timedelta.max


def spec(**overrides) -> dict:
    return {
        "name": "Weekday regression",
        "cron": "0 9 * * 1-5",
        "timezone": "Europe/Berlin",
    } | overrides


class TestSpecValidation:
    def test_valid_spec_normalizes_spacing(self):
        assert ScheduleSpecIn(**spec(cron="0  9 * *   1-5")).cron == "0 9 * * 1-5"

    @pytest.mark.parametrize("expression", ["* * * * *", "*/30 * * * *", "0,59 9 * * *"])
    def test_cron_under_the_minimum_is_refused(self, expression):
        with pytest.raises(ValidationError, match="at most once every 60 minutes"):
            ScheduleSpecIn(**spec(cron=expression))

    def test_lowered_minimum_allows_a_tighter_cron(self):
        with patch(
            "rhesis.backend.app.schemas.test_run_schedule.get_application_settings"
        ) as settings:
            settings.return_value.schedule_min_interval_minutes = 15
            assert ScheduleSpecIn(**spec(cron="*/15 * * * *")).cron == "*/15 * * * *"
            with pytest.raises(ValidationError, match="every 15 minutes"):
                ScheduleSpecIn(**spec(cron="*/5 * * * *"))

    def test_six_field_cron_is_refused(self):
        with pytest.raises(ValidationError, match="5 fields"):
            ScheduleSpecIn(**spec(cron="0 0 9 * * 1-5"))

    def test_nonsense_cron_is_refused(self):
        with pytest.raises(ValidationError, match="isn't valid"):
            ScheduleSpecIn(**spec(cron="61 9 * * *"))

    def test_unknown_time_zone_is_refused(self):
        with pytest.raises(ValidationError, match="Unknown time zone"):
            ScheduleSpecIn(**spec(timezone="Mars/Olympus"))

    def test_past_run_at_is_refused(self):
        with pytest.raises(ValidationError, match="in the future"):
            ScheduleSpecIn(**spec(cron=None, run_at=utc(2020, 1, 1)))

    def test_past_end_is_refused(self):
        with pytest.raises(ValidationError, match="end date"):
            ScheduleSpecIn(**spec(ends_at=utc(2020, 1, 1)))

    def test_exactly_one_of_cron_and_run_at(self):
        with pytest.raises(ValidationError, match="either"):
            ScheduleSpecIn(**spec(run_at=datetime.now(UTC) + timedelta(days=1)))
        with pytest.raises(ValidationError, match="either"):
            ScheduleSpecIn(**spec(cron=None))

    def test_exception_skips_or_moves(self):
        ScheduleException(occurrence=utc(2027, 1, 1), skip=True)
        ScheduleException(occurrence=utc(2027, 1, 1), run_at=utc(2027, 1, 2))
        with pytest.raises(ValidationError):
            ScheduleException(occurrence=utc(2027, 1, 1))
        with pytest.raises(ValidationError):
            ScheduleException(occurrence=utc(2027, 1, 1), skip=True, run_at=utc(2027, 1, 2))


class TestDescribe:
    @pytest.mark.parametrize(
        ("expression", "words"),
        [
            ("0 * * * *", "Every hour"),
            ("15 * * * *", "Every hour at :15"),
            ("0 9 * * *", "Every day at 09:00"),
            ("0 9 * * 1-5", "Every weekday at 09:00"),
            ("30 7 * * 1", "Every Monday at 07:30"),
            ("0 9 * * 1,4", "Every Monday and Thursday at 09:00"),
            ("0 9 * * 0,6", "Every Saturday and Sunday at 09:00"),
            ("0 9 * * 1,3,5", "Every Monday, Wednesday and Friday at 09:00"),
            ("0 9 1 * *", "Every month on the 1st at 09:00"),
            ("0 9 22 * *", "Every month on the 22nd at 09:00"),
            ("0 9 L * *", "Every month on the last day at 09:00"),
        ],
    )
    def test_presets(self, expression, words):
        assert describe_schedule(cron(expression)) == words

    @pytest.mark.parametrize("expression", ["0 9-17/2 * * *", "0 9 1 1 *", "0 9 1 * 1"])
    def test_custom_cron_never_shows_the_expression(self, expression):
        assert describe_schedule(cron(expression)) == "Custom schedule"

    def test_run_once_uses_the_schedules_time_zone(self):
        timing = ScheduleTiming(None, berlin(2026, 11, 13, 22), "Europe/Berlin")
        assert describe_schedule(timing) == "Once on Fri 13 Nov at 22:00"


class TestOverdue:
    def test_overdue_only_past_the_margin(self):
        now = utc(2026, 11, 25, 9, 0)
        assert not is_overdue(now - timedelta(minutes=2), now)
        assert is_overdue(now - timedelta(minutes=2, seconds=1), now)
        assert not is_overdue(None, now)

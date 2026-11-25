"""When a test run schedule runs. Pure functions, no database.

All instants in and out are timezone-aware UTC. Cron expressions are read in the schedule's own
time zone, so "09:00" stays 09:00 local across DST changes.
"""

import itertools
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError, available_timezones

from croniter import CroniterBadCronError, CroniterBadDateError, croniter

OVERDUE_MARGIN = timedelta(minutes=2)

# Upper bound on candidates looked at in one call, so a sparse or odd expression can't spin.
_MAX_CANDIDATES = 5000

_DAY_NAMES = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]


@dataclass(frozen=True)
class ScheduleTiming:
    """The parts of a schedule that decide when it runs."""

    cron: str | None
    run_at: datetime | None
    timezone: str
    ends_at: datetime | None = None

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ScheduleTiming":
        return cls(
            cron=data.get("cron"),
            run_at=parse_instant(data.get("run_at")),
            timezone=data.get("timezone") or "UTC",
            ends_at=parse_instant(data.get("ends_at")),
        )

    @property
    def zone(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)


@dataclass(frozen=True)
class Occurrence:
    """One run of a schedule. ``original`` is when the schedule puts it, ``at`` when it runs."""

    original: datetime
    at: datetime

    @property
    def changed(self) -> bool:
        return self.at != self.original


# --- parsing and validation -------------------------------------------------------------------


def parse_instant(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        instant = value
    else:
        instant = datetime.fromisoformat(str(value))
    if instant.tzinfo is None:
        raise ValueError(f"{value} has no time zone")
    return instant.astimezone(timezone.utc)


def format_instant(value: datetime | None) -> str | None:
    return value.astimezone(timezone.utc).isoformat() if value else None


def check_timezone(name: str) -> str:
    try:
        ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValueError(f"Unknown time zone: {name}") from exc
    if name not in available_timezones() and name != "UTC":
        raise ValueError(f"Unknown time zone: {name}")
    return name


def check_cron(expression: str) -> str:
    """Accept a standard 5-field expression that has at least one future match."""
    expression = " ".join(expression.split())
    if len(expression.split(" ")) != 5:
        raise ValueError("Enter a cron expression with 5 fields: minute hour day month weekday.")
    if not croniter.is_valid(expression):
        raise ValueError("This cron expression isn't valid.")
    try:
        croniter(expression, datetime.now(timezone.utc)).get_next(datetime)
    except (CroniterBadCronError, CroniterBadDateError) as exc:
        raise ValueError("This cron expression never runs.") from exc
    return expression


# --- iteration --------------------------------------------------------------------------------


def _is_second_of_repeated_time(local: datetime, zone: ZoneInfo) -> bool:
    """True for the later of two instants that share a wall-clock time (autumn DST change)."""
    earlier = local.replace(tzinfo=None).replace(tzinfo=zone, fold=0)
    return earlier.utcoffset() != local.utcoffset()


def _originals_after(timing: ScheduleTiming, after: datetime) -> Iterator[datetime]:
    """The schedule's own times strictly after ``after``, in order, up to ``ends_at``."""
    if timing.run_at is not None:
        if timing.run_at > after and (timing.ends_at is None or timing.run_at <= timing.ends_at):
            yield timing.run_at
        return
    if not timing.cron:
        return
    zone = timing.zone
    iterator = croniter(timing.cron, after.astimezone(zone))
    for _ in range(_MAX_CANDIDATES):
        try:
            local = iterator.get_next(datetime)
        except CroniterBadDateError:
            return
        if _is_second_of_repeated_time(local, zone):
            continue
        instant = local.astimezone(timezone.utc)
        if timing.ends_at is not None and instant > timing.ends_at:
            return
        yield instant


def _is_original(timing: ScheduleTiming, instant: datetime) -> bool:
    return next(_originals_after(timing, instant - timedelta(seconds=1)), None) == instant


def _exception_map(exceptions: Iterable[Mapping[str, Any]]) -> dict[datetime, datetime | None]:
    """Original time to its new time, or ``None`` when that run is skipped."""
    result: dict[datetime, datetime | None] = {}
    for entry in exceptions or ():
        original = parse_instant(entry["occurrence"])
        result[original] = None if entry.get("skip") else parse_instant(entry.get("run_at"))
    return result


def occurrences(
    timing: ScheduleTiming,
    start: datetime,
    end: datetime,
    exceptions: Iterable[Mapping[str, Any]] = (),
    limit: int | None = None,
) -> list[Occurrence]:
    """Runs whose time falls in ``[start, end)``, with skips and moves applied, in time order.

    ``limit`` caps how many are returned, e.g. the runs left under ``max_runs``.
    """
    changes = _exception_map(exceptions)
    result = []
    for original in _originals_after(timing, start - timedelta(microseconds=1)):
        if original >= end:
            break
        if original in changes:
            continue
        result.append(Occurrence(original, original))
    for original, moved_to in changes.items():
        if moved_to is not None and start <= moved_to < end and _is_original(timing, original):
            result.append(Occurrence(original, moved_to))
    result.sort(key=lambda occurrence: occurrence.at)
    return result[:limit] if limit is not None else result


def compute_next_run(
    timing: ScheduleTiming,
    after: datetime,
    exceptions: Iterable[Mapping[str, Any]] = (),
) -> Occurrence | None:
    """The first run strictly after ``after``, with skips and moves applied."""
    changes = _exception_map(exceptions)
    candidates = []
    for original in _originals_after(timing, after):
        if original not in changes:
            candidates.append(Occurrence(original, original))
            break
    for original, moved_to in changes.items():
        if moved_to is not None and moved_to > after and _is_original(timing, original):
            candidates.append(Occurrence(original, moved_to))
    return min(candidates, key=lambda occurrence: occurrence.at, default=None)


def min_gap(timing: ScheduleTiming, sample: int = 50, start: datetime | None = None) -> timedelta:
    """The shortest real time between two runs across the next ``sample`` runs."""
    if timing.cron is None:
        return timedelta.max
    times = []
    for instant in _originals_after(timing, start or datetime.now(timezone.utc)):
        times.append(instant)
        if len(times) > sample:
            break
    gaps = [later - earlier for earlier, later in itertools.pairwise(times)]
    return min(gaps, default=timedelta.max)


def is_overdue(next_run_at: datetime | None, now: datetime, margin: timedelta = OVERDUE_MARGIN):
    """A run is overdue once it is more than ``margin`` past its time and still hasn't started."""
    return next_run_at is not None and now - next_run_at > margin


def prune_exceptions(
    exceptions: Iterable[Mapping[str, Any]], last_fired: datetime | None
) -> list[dict[str, Any]]:
    """Drop exceptions whose run, original or moved, is at or before ``last_fired``."""
    if last_fired is None:
        return [dict(entry) for entry in exceptions or ()]
    kept = []
    for entry in exceptions or ():
        latest = max(
            parse_instant(entry["occurrence"]), parse_instant(entry.get("run_at")) or last_fired
        )
        if latest > last_fired:
            kept.append(dict(entry))
    return kept


# --- plain-language description ---------------------------------------------------------------


def _ordinal(day: int) -> str:
    suffix = "th" if 11 <= day % 100 <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
    return f"{day}{suffix}"


def _join_words(words: list[str]) -> str:
    return words[0] if len(words) == 1 else f"{', '.join(words[:-1])} and {words[-1]}"


def _weekdays(field: str) -> list[int] | None:
    days: set[int] = set()
    for part in field.split(","):
        if "-" in part:
            first, last = part.split("-", 1)
            if not (first.isdigit() and last.isdigit()) or int(first) > int(last):
                return None
            days.update(range(int(first), int(last) + 1))
        elif part.isdigit():
            days.add(int(part))
        else:
            return None
    days = {0 if day == 7 else day for day in days}
    return sorted(days) if days and max(days) <= 6 else None


def _describe_cron(expression: str) -> str | None:
    minute, hour, day_of_month, month, day_of_week = expression.split()
    if not minute.isdigit() or month != "*":
        return None
    if hour == "*" and day_of_month == "*" and day_of_week == "*":
        return "Every hour" if int(minute) == 0 else f"Every hour at :{int(minute):02d}"
    if not hour.isdigit():
        return None
    at = f"at {int(hour):02d}:{int(minute):02d}"
    if day_of_month == "*" and day_of_week == "*":
        return f"Every day {at}"
    if day_of_week == "*":
        if day_of_month == "L":
            return f"Every month on the last day {at}"
        if day_of_month.isdigit():
            return f"Every month on the {_ordinal(int(day_of_month))} {at}"
        return None
    days = _weekdays(day_of_week) if day_of_month == "*" else None
    if days is None:
        return None
    if days == [1, 2, 3, 4, 5]:
        return f"Every weekday {at}"
    if len(days) == 7:
        return f"Every day {at}"
    # Monday first, the way the drawer's day toggles are ordered.
    ordered = sorted(days, key=lambda day: (day == 0, day))
    return f"Every {_join_words([_DAY_NAMES[day] for day in ordered])} {at}"


def describe_schedule(timing: ScheduleTiming) -> str:
    """Plain words for when a schedule runs. Never shows the cron expression."""
    if timing.run_at is not None:
        local = timing.run_at.astimezone(timing.zone)
        return f"Once on {local:%a} {local.day} {local:%b} at {local:%H:%M}"
    if timing.cron:
        return _describe_cron(timing.cron) or "Custom schedule"
    return "Not scheduled"

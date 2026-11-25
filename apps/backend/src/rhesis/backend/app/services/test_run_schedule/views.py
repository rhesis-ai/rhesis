"""What the schedule API returns: list items, the detail page, the calendar window, previews."""

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from rhesis.backend.app.crud.test_configuration import (
    count_schedule_runs,
    list_configuration_run_ids,
    list_schedules,
    recent_configuration_runs,
)
from rhesis.backend.app.crud.test_run import empty_usage, get_usage_statistics_for_runs
from rhesis.backend.app.models.test_configuration import TestConfiguration
from rhesis.backend.app.models.test_run import TestRun
from rhesis.backend.app.schemas.test_run_schedule import (
    OccurrenceOut,
    OccurrencesOut,
    ScheduleSpecIn,
)
from rhesis.backend.app.services.test_run_schedule import timing
from rhesis.backend.app.services.test_run_schedule.service import (
    schedule_of,
    status_of,
    timing_of,
)

# The calendar asks for at most six weeks at a time.
MAX_WINDOW = timedelta(days=42)
UPCOMING_COUNT = 5
# Hourly schedules go in a strip above the calendar instead of on every day.
HOURLY = timedelta(hours=1)
# "Expected per month" needs a few runs before it means anything.
MIN_RUNS_FOR_ESTIMATE = 3


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _named(obj, **extra) -> dict | None:
    return {"id": obj.id, "name": getattr(obj, "name", None), **extra} if obj else None


def _owner(config: TestConfiguration) -> dict | None:
    user = config.user
    if user is None:
        return None
    return {"id": user.id, "name": user.display_name}


def _run_stats(db: Session, runs: list[TestRun], organization_id: str) -> dict[str, dict]:
    from rhesis.backend.jobs.execution.result_processor import get_test_statistics_for_runs

    return get_test_statistics_for_runs(db, [r.id for r in runs], organization_id=organization_id)


def _run_summary(run: TestRun, stats: dict | None, usage: dict | None) -> dict[str, Any]:
    attributes = run.attributes or {}
    started = timing.parse_instant(attributes.get("started_at"))
    completed = timing.parse_instant(attributes.get("completed_at"))
    total = (stats or {}).get("total") or 0
    return {
        "id": run.id,
        "name": run.name,
        "status": run.status.name if run.status else None,
        "pass_rate": (stats["passed"] / total) if total else None,
        "started_at": started or run.created_at,
        "duration_s": (completed - started).total_seconds() if started and completed else None,
        "total_cost_usd": (usage or {}).get("total_cost_usd"),
        "trigger": attributes.get("trigger", "manual"),
        "scheduled_for": timing.parse_instant(attributes.get("scheduled_for")),
    }


def schedule_item(
    config: TestConfiguration, last_run: dict | None = None, now: datetime | None = None
) -> dict[str, Any]:
    """A schedule as a list row. ``overdue`` is worked out here, never stored."""
    schedule = schedule_of(config)
    next_run_at = timing.parse_instant(schedule.get("next_run_at"))
    status = status_of(config)
    endpoint = config.endpoint
    return {
        "id": config.id,
        "name": schedule.get("name") or "",
        "status": status,
        "overdue": status == "Scheduled" and timing.is_overdue(next_run_at, now or _now()),
        "repeats": timing.describe_schedule(timing_of(schedule)),
        "cron": schedule.get("cron"),
        "run_at": schedule.get("run_at"),
        "timezone": schedule.get("timezone") or "UTC",
        "next_run_at": next_run_at,
        "ends_at": schedule.get("ends_at"),
        "max_runs": schedule.get("max_runs"),
        "notify": schedule.get("notify") or "problems",
        "paused_reason": schedule.get("paused_reason"),
        "last_skip": schedule.get("last_skip"),
        "test_set": _named(config.test_set),
        "endpoint": _named(endpoint, connection_type=getattr(endpoint, "connection_type", None)),
        "owner": _owner(config),
        "user_id": config.user_id,
        "created_at": config.created_at,
        "last_run": last_run,
    }


def list_items(
    db: Session, organization_id: str, *, test_set_id=None, status_names=None
) -> list[dict[str, Any]]:
    configs = list_schedules(db, test_set_id=test_set_id, status_names=status_names)
    last_runs = {c.id: (recent_configuration_runs(db, c.id, limit=1) or [None])[0] for c in configs}
    runs = [r for r in last_runs.values() if r is not None]
    stats = _run_stats(db, runs, organization_id) if runs else {}
    items = []
    for config in configs:
        run = last_runs[config.id]
        summary = _run_summary(run, stats.get(str(run.id)), None) if run else None
        items.append(schedule_item(config, summary))
    return items


def _usage(db: Session, config: TestConfiguration, organization_id: str) -> dict[str, Any]:
    """Totals over every run of the configuration, Run now included."""
    run_ids = list_configuration_run_ids(db, config.id)
    if not run_ids:
        return {"run_count": 0}
    per_run = get_usage_statistics_for_runs(db, run_ids, organization_id=organization_id)
    totals = empty_usage()
    for usage in per_run.values():
        for field in ("total_tokens", "total_input_tokens", "total_output_tokens"):
            totals[field] += usage.get(field) or 0
        totals["total_cost_usd"] += float(usage.get("total_cost_usd") or 0)
    oldest = recent_configuration_runs(db, config.id, limit=1, offset=len(run_ids) - 1)
    first_run_at = oldest[0].created_at if oldest else None
    count = len(run_ids)
    return {
        "run_count": count,
        "first_run_at": first_run_at,
        "total_cost_usd": totals["total_cost_usd"],
        "total_tokens": totals["total_tokens"],
        "input_tokens": totals["total_input_tokens"],
        "output_tokens": totals["total_output_tokens"],
        "avg_cost_usd": totals["total_cost_usd"] / count,
        "expected_month_usd": _expected_month(config, totals["total_cost_usd"] / count),
    }


def _expected_month(config: TestConfiguration, avg_cost: float) -> float | None:
    """Average cost per run times the runs planned in the next 30 days."""
    schedule = schedule_of(config)
    if status_of(config) != "Scheduled":
        return None
    now = _now()
    planned = timing.occurrences(
        timing_of(schedule), now, now + timedelta(days=30), schedule.get("exceptions") or []
    )
    return round(avg_cost * len(planned), 2)


def _run_settings(config: TestConfiguration) -> dict[str, Any]:
    attributes = config.attributes or {}
    return {
        "metrics_source": attributes.get("metrics_source"),
        "metrics": attributes.get("metrics") or [],
        "execution_model_id": attributes.get("execution_model_id"),
        "evaluation_model_id": attributes.get("evaluation_model_id"),
        "execution_mode": attributes.get("execution_mode"),
    }


def detail(
    db: Session, config: TestConfiguration, organization_id: str, runs_limit=10, runs_offset=0
) -> dict[str, Any]:
    """Everything the schedule page shows."""
    runs = recent_configuration_runs(db, config.id, limit=runs_limit, offset=runs_offset)
    stats = _run_stats(db, runs, organization_id) if runs else {}
    usage = (
        get_usage_statistics_for_runs(db, [r.id for r in runs], organization_id=organization_id)
        if runs
        else {}
    )
    summaries = [_run_summary(r, stats.get(str(r.id)), usage.get(str(r.id))) for r in runs]
    totals = _usage(db, config, organization_id)
    if totals["run_count"] < MIN_RUNS_FOR_ESTIMATE:
        totals["expected_month_usd"] = None
    return schedule_item(config, summaries[0] if runs_offset == 0 and summaries else None) | {
        "upcoming": [o.at for o in upcoming(db, config, UPCOMING_COUNT)],
        "recent_runs": summaries,
        "usage": totals,
        "run_settings": _run_settings(config),
    }


def upcoming(db: Session, config: TestConfiguration, count: int) -> list[timing.Occurrence]:
    if status_of(config) != "Scheduled":
        return []
    schedule = schedule_of(config)
    limit = count
    if schedule.get("max_runs") is not None:
        limit = min(count, max(schedule["max_runs"] - count_schedule_runs(db, config.id), 0))
    now = _now()
    return timing.occurrences(
        timing_of(schedule),
        now,
        now + timedelta(days=400),
        schedule.get("exceptions") or [],
        limit=limit,
    )


def occurrence_window(db: Session, start: datetime, end: datetime) -> dict[str, Any]:
    """Runs of every active schedule in ``[start, end)``, for the calendar."""
    if end <= start or end - start > MAX_WINDOW:
        raise ValueError("Ask for a window of up to 42 days.")
    items, hourly = [], []
    for config in list_schedules(db, status_names=["Scheduled"]):
        schedule = schedule_of(config)
        schedule_timing = timing_of(schedule)
        if schedule_timing.cron and timing.min_gap(schedule_timing, sample=24) <= HOURLY:
            hourly.append({"id": config.id, "name": schedule.get("name")})
            continue
        now = _now()
        window_start = max(start, now)
        exceptions = schedule.get("exceptions") or []
        if schedule.get("max_runs") is not None:
            # Counted from now, like upcoming(): only the runs left under the limit.
            left = max(schedule["max_runs"] - count_schedule_runs(db, config.id), 0)
            window = [
                o
                for o in timing.occurrences(schedule_timing, now, end, exceptions, limit=left)
                if o.at >= window_start
            ]
        else:
            window = timing.occurrences(schedule_timing, window_start, end, exceptions)
        for occurrence in window:
            items.append(
                OccurrenceOut(
                    schedule_id=config.id,
                    name=schedule.get("name") or "",
                    occurrence=occurrence.original,
                    at=occurrence.at,
                    changed=occurrence.changed,
                )
            )
    items.sort(key=lambda item: item.at)
    return OccurrencesOut(items=items, hourly=hourly).model_dump()


def preview(spec: ScheduleSpecIn, count: int = 3) -> dict[str, Any]:
    now = _now()
    schedule_timing = spec.to_timing()
    upcoming_runs = timing.occurrences(schedule_timing, now, now + timedelta(days=400), limit=count)
    if spec.max_runs is not None:
        upcoming_runs = upcoming_runs[: spec.max_runs]
    return {
        "repeats": timing.describe_schedule(schedule_timing),
        "next": [o.at for o in upcoming_runs],
    }

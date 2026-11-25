from datetime import datetime, timedelta, timezone
from typing import Literal

from pydantic import (
    UUID4,
    AwareDatetime,
    BaseModel,
    Field,
    PositiveInt,
    ValidationInfo,
    model_validator,
)

from rhesis.backend.app.config.settings import get_application_settings
from rhesis.backend.app.schemas.test_set import TestSetExecutionRequest
from rhesis.backend.app.services.test_run_schedule import timing

ScheduleNotify = Literal["always", "problems", "never"]


class ScheduleException(BaseModel):
    """A change to one run of a schedule, keyed by the time the schedule originally put it."""

    occurrence: AwareDatetime
    skip: bool = False
    run_at: AwareDatetime | None = None
    # A run kept from the timetable before a "this and following" edit.
    extra: bool = False

    @model_validator(mode="after")
    def _skip_or_move(self) -> "ScheduleException":
        if self.skip == (self.run_at is not None):
            raise ValueError("An exception either skips the run or moves it, not both.")
        if self.extra and self.skip:
            raise ValueError("An extra run can't also be a skip.")
        return self


class ScheduleSpecIn(BaseModel):
    """When and how a schedule runs, as sent by the client."""

    name: str = Field(min_length=1, max_length=200)
    cron: str | None = None
    run_at: AwareDatetime | None = None
    timezone: str = "UTC"
    ends_at: AwareDatetime | None = None
    max_runs: PositiveInt | None = None
    notify: ScheduleNotify = "problems"

    @model_validator(mode="after")
    def _check(self, info: ValidationInfo) -> "ScheduleSpecIn":
        # Fields carried over unchanged from a stored schedule may already be in the past.
        unchanged = (info.context or {}).get("unchanged", set())
        if (self.cron is None) == (self.run_at is None):
            raise ValueError("Choose either a date to run once or a repeating schedule.")
        self.timezone = timing.check_timezone(self.timezone)
        now = datetime.now(timezone.utc)
        if self.run_at is not None and self.run_at <= now and "run_at" not in unchanged:
            raise ValueError("Pick a time in the future.")
        if self.ends_at is not None and self.ends_at <= now and "ends_at" not in unchanged:
            raise ValueError("Pick an end date in the future.")
        if self.cron is not None:
            self.cron = timing.check_cron(self.cron)
            minimum = get_application_settings().schedule_min_interval_minutes
            if timing.min_gap(self.to_timing()) < timedelta(minutes=minimum):
                raise ValueError(f"Schedules can run at most once every {minimum} minutes.")
        return self

    def to_timing(self) -> timing.ScheduleTiming:
        return timing.ScheduleTiming(
            cron=self.cron,
            run_at=self.run_at,
            timezone=self.timezone,
            ends_at=self.ends_at,
        )


# Spec fields an update may set; anything left out keeps its stored value.
SPEC_FIELDS = ("name", "cron", "run_at", "timezone", "ends_at", "max_runs", "notify")
TIMING_FIELDS = ("cron", "run_at", "timezone", "ends_at", "max_runs")


class ScheduleUpdate(BaseModel):
    """A change to a schedule. Only the fields sent change."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    cron: str | None = None
    run_at: AwareDatetime | None = None
    timezone: str | None = None
    ends_at: AwareDatetime | None = None
    max_runs: PositiveInt | None = None
    notify: ScheduleNotify | None = None
    test_set_id: UUID4 | None = None
    endpoint_id: UUID4 | None = None
    run_settings: TestSetExecutionRequest | None = None

    def spec_changes(self) -> dict:
        return {f: getattr(self, f) for f in SPEC_FIELDS if f in self.model_fields_set}

    def touches_timing(self) -> bool:
        return any(f in self.model_fields_set for f in TIMING_FIELDS)

    def touches_settings(self) -> bool:
        return bool(self.model_fields_set & {"endpoint_id", "run_settings", "name", "notify"})


class OccurrenceEdit(ScheduleUpdate):
    """A change made from one run on the calendar. ``move_to`` is that run's new time."""

    move_to: AwareDatetime | None = None

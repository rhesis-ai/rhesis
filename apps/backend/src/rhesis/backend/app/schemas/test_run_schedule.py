from datetime import datetime, timedelta, timezone
from typing import Literal

from pydantic import AwareDatetime, BaseModel, Field, PositiveInt, model_validator

from rhesis.backend.app.config.settings import get_application_settings
from rhesis.backend.app.services.test_run_schedule import timing

ScheduleNotify = Literal["always", "problems", "never"]


class ScheduleException(BaseModel):
    """A change to one run of a schedule, keyed by the time the schedule originally put it."""

    occurrence: AwareDatetime
    skip: bool = False
    run_at: AwareDatetime | None = None

    @model_validator(mode="after")
    def _skip_or_move(self) -> "ScheduleException":
        if self.skip == (self.run_at is not None):
            raise ValueError("An exception either skips the run or moves it, not both.")
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
    def _check(self) -> "ScheduleSpecIn":
        if (self.cron is None) == (self.run_at is None):
            raise ValueError("Choose either a date to run once or a repeating schedule.")
        self.timezone = timing.check_timezone(self.timezone)
        now = datetime.now(timezone.utc)
        if self.run_at is not None and self.run_at <= now:
            raise ValueError("Pick a time in the future.")
        if self.ends_at is not None and self.ends_at <= now:
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

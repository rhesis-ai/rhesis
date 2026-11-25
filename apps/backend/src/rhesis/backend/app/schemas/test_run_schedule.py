from datetime import datetime, timedelta, timezone
from typing import ClassVar, Literal

from pydantic import (
    UUID4,
    AwareDatetime,
    BaseModel,
    Field,
    PositiveInt,
    ValidationInfo,
    model_validator,
)

from rhesis.backend.app.auth.capabilities import ResourceType
from rhesis.backend.app.config.settings import get_application_settings
from rhesis.backend.app.schemas.affordances import WithPermittedActions
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

    # Blank on create means "name it after the test set".
    name: str = Field(default="", max_length=200)
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

    def changes_times(self) -> bool:
        """When the runs fall, not just when the schedule ends."""
        return bool(self.model_fields_set & {"cron", "run_at", "timezone"})

    def touches_settings(self) -> bool:
        return bool(self.model_fields_set & {"endpoint_id", "run_settings", "name", "notify"})


class OccurrenceEdit(ScheduleUpdate):
    """A change made from one run on the calendar. ``move_to`` is that run's new time."""

    move_to: AwareDatetime | None = None


# --- requests ---------------------------------------------------------------------------------


class ScheduleCreate(BaseModel):
    """Schedule a test set (or several, one schedule each) against an endpoint."""

    test_set_id: UUID4 | None = None
    test_set_ids: list[UUID4] | None = None
    endpoint_id: UUID4
    schedule: ScheduleSpecIn
    run_settings: TestSetExecutionRequest | None = None

    @model_validator(mode="after")
    def _one_or_many(self) -> "ScheduleCreate":
        if (self.test_set_id is None) == (not self.test_set_ids):
            raise ValueError("Send either test_set_id or test_set_ids.")
        return self


# --- responses --------------------------------------------------------------------------------


class NamedRef(BaseModel):
    id: UUID4
    name: str | None = None


class EndpointRef(NamedRef):
    connection_type: str | None = None


class ScheduleRunSummary(BaseModel):
    id: UUID4
    name: str | None = None
    status: str | None = None
    pass_rate: float | None = None
    started_at: datetime | None = None
    duration_s: float | None = None
    total_cost_usd: float | None = None
    trigger: str | None = None
    scheduled_for: datetime | None = None


class LastSkip(BaseModel):
    at: datetime
    reason: str


class TestRunScheduleOut(WithPermittedActions):
    __resource_type__: ClassVar[str | None] = ResourceType.TEST_RUN

    id: UUID4
    name: str
    status: str | None = None
    overdue: bool = False
    repeats: str
    cron: str | None = None
    run_at: datetime | None = None
    timezone: str
    next_run_at: datetime | None = None
    ends_at: datetime | None = None
    max_runs: int | None = None
    notify: ScheduleNotify
    paused_reason: str | None = None
    last_skip: LastSkip | None = None
    test_set: NamedRef | None = None
    endpoint: EndpointRef | None = None
    owner: NamedRef | None = None
    # The owner, read by WithPermittedActions for ownership-gated actions.
    user_id: UUID4 | None = None
    created_at: datetime | None = None
    last_run: ScheduleRunSummary | None = None


class ScheduleUsage(BaseModel):
    run_count: int = 0
    first_run_at: datetime | None = None
    total_cost_usd: float = 0
    total_tokens: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    avg_cost_usd: float | None = None
    expected_month_usd: float | None = None


class RunSettingsOut(BaseModel):
    metrics_source: str | None = None
    metrics: list[dict] = Field(default_factory=list)
    execution_model_id: str | None = None
    evaluation_model_id: str | None = None
    execution_mode: str | None = None


class TestRunScheduleDetail(TestRunScheduleOut):
    upcoming: list[datetime] = Field(default_factory=list)
    recent_runs: list[ScheduleRunSummary] = Field(default_factory=list)
    usage: ScheduleUsage = Field(default_factory=ScheduleUsage)
    run_settings: RunSettingsOut = Field(default_factory=RunSettingsOut)


class OccurrenceOut(BaseModel):
    schedule_id: UUID4
    name: str
    occurrence: datetime
    at: datetime
    changed: bool = False


class OccurrencesOut(BaseModel):
    items: list[OccurrenceOut]
    hourly: list[NamedRef]


class SchedulePreview(BaseModel):
    repeats: str
    next: list[datetime]

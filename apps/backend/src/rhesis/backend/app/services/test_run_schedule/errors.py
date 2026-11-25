"""Errors raised by the test run schedule service, mapped to HTTP statuses by the router."""


class ScheduleError(Exception):
    """Base class for schedule errors."""


class ScheduleValidationError(ScheduleError, ValueError):
    """The request can't be applied to this schedule (422)."""


class ScheduleConflict(ScheduleError):
    """The schedule changed in a way that makes the request stale (409)."""


class ScheduleNotFound(ScheduleError):
    """No schedule with that id in the caller's scope (404)."""

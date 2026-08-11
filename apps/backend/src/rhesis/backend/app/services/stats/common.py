"""Shared utilities for statistics functions."""

from datetime import datetime, timedelta, timezone

from rhesis.backend.app.constants import OverallTestResult


def parse_date_range(
    start_date: str | None,
    end_date: str | None,
    months: int | None = None,
) -> tuple[datetime | None, datetime | None]:
    """Optional date bounds. None means open-ended / all time.

    - months → last N months (cannot combine with start/end)
    - start_date → from then onwards
    - end_date → up to then
    - both → closed range
    - none → (None, None)
    """
    if months is not None:
        if start_date is not None or end_date is not None:
            raise ValueError("Use either months or start_date/end_date, not both")
        end = datetime.now(timezone.utc)
        return end - timedelta(days=30 * months), end

    start = datetime.fromisoformat(start_date.replace("Z", "+00:00")) if start_date else None
    end = datetime.fromisoformat(end_date.replace("Z", "+00:00")) if end_date else None
    return start, end


def automated_metric_success(data: dict) -> bool:
    """Return the pre-review automated metric outcome from stored JSON."""
    override = data.get("override")
    if isinstance(override, dict) and "original_value" in override:
        return bool(override["original_value"])
    return bool(data["is_successful"])


def effective_metric_success(
    overall_result: str | None,
    is_successful: bool,
    has_metric_override: bool,
) -> bool:
    """Return whether a metric counts as passed in aggregate stats.

    Metric-level reviews update ``is_successful`` directly (``has_metric_override``
    is True). Test-result-level reviews only update ``status_id`` / ``result``, so
    when overall passed/failed disagrees with the stored metric value, prefer the
    overall outcome.
    """
    if has_metric_override:
        return is_successful

    if overall_result == OverallTestResult.PASSED and not is_successful:
        return True
    if overall_result == OverallTestResult.FAILED and is_successful:
        return False

    return is_successful

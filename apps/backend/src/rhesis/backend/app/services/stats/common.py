"""Shared utilities for statistics functions."""

from datetime import datetime, timedelta
from typing import Any, Dict, List


def parse_date_range(
    start_date: str | None, end_date: str | None, months: int
) -> tuple[datetime, datetime]:
    """Parse and validate date range parameters.

    Returns (start_date_obj, end_date_obj). If explicit dates are provided they
    take precedence; otherwise the range spans the last *months* months.
    """
    if start_date and end_date:
        start_date_obj = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
        end_date_obj = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
    else:
        end_date_obj = datetime.utcnow()
        start_date_obj = end_date_obj - timedelta(days=30 * months)
    return start_date_obj, end_date_obj


def build_pass_rate_stats(stats_dict: Dict[str, Dict[str, int]]) -> Dict[str, Dict[str, Any]]:
    """Convert ``{name: {passed, failed}}`` into ``{name: {total, passed, failed, pass_rate}}``."""
    pass_rates = {}
    for name, stats in stats_dict.items():
        total = stats["passed"] + stats["failed"]
        pass_rate = round((stats["passed"] / total) * 100, 2) if total > 0 else 0
        pass_rates[name] = {
            "total": total,
            "passed": stats["passed"],
            "failed": stats["failed"],
            "pass_rate": pass_rate,
        }
    return pass_rates


def build_response_data(
    mode: str, mode_definitions: Dict[str, List[str]], **data_sections
) -> Dict[str, Any]:
    """Return only the data sections requested by *mode*, always including metadata."""
    response = {"metadata": data_sections.get("metadata", {})}
    required_sections = mode_definitions.get(mode, mode_definitions.get("all", []))
    for section in required_sections:
        if section in data_sections:
            response[section] = data_sections[section]
    return response


def build_metadata(
    organization_id: str | None,
    start_date_obj: datetime,
    end_date_obj: datetime,
    months: int,
    mode: str,
    total_items: int,
    **additional_metadata,
) -> Dict[str, Any]:
    """Build the standard metadata dict attached to every stats response."""
    metadata = {
        "generated_at": datetime.utcnow().isoformat(),
        "organization_id": organization_id,
        "period": f"Last {months} months",
        "start_date": start_date_obj.isoformat(),
        "end_date": end_date_obj.isoformat(),
        "total_items": total_items,
        "mode": mode,
    }
    metadata.update(additional_metadata)
    return metadata


def build_empty_stats_response(
    mode: str,
    mode_definitions: Dict[str, List[str]],
    start_date_obj: datetime,
    end_date_obj: datetime,
    months: int,
    organization_id: str | None,
    **additional_metadata,
) -> Dict[str, Any]:
    """Build an empty stats response when no data matches the filters."""
    metadata = build_metadata(
        organization_id=organization_id,
        start_date_obj=start_date_obj,
        end_date_obj=end_date_obj,
        months=months,
        mode=mode,
        total_items=0,
        **additional_metadata,
    )

    empty_data = {
        "metadata": metadata,
        "status_distribution": [],
        "result_distribution": {
            "total": 0,
            "passed": 0,
            "failed": 0,
            "pending": 0,
            "pass_rate": 0,
        },
        "timeline": [],
        "overall_pass_rates": {"total": 0, "passed": 0, "failed": 0, "pass_rate": 0},
        "metric_pass_rates": {},
        "behavior_pass_rates": {},
        "category_pass_rates": {},
        "topic_pass_rates": {},
        "test_run_summary": [],
        "most_run_test_sets": [],
        "top_executors": [],
        "overall_summary": {
            "total_runs": 0,
            "unique_test_sets": 0,
            "unique_executors": 0,
            "most_common_status": "unknown",
            "pass_rate": 0,
        },
    }

    return build_response_data(mode, mode_definitions, **empty_data)

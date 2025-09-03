"""Common utilities for statistics functions with shared filtering and helper methods."""

from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from sqlalchemy.orm import Session


def parse_date_range(start_date: str | None, end_date: str | None, months: int) -> tuple[datetime, datetime]:
    """
    Parse and validate date range parameters.
    
    Args:
        start_date: Optional start date in ISO format
        end_date: Optional end date in ISO format  
        months: Number of months to include if no date range specified
        
    Returns:
        Tuple of (start_date_obj, end_date_obj)
    """
    if start_date and end_date:
        start_date_obj = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        end_date_obj = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
    else:
        end_date_obj = datetime.utcnow()
        start_date_obj = end_date_obj - timedelta(days=30 * months)
    
    return start_date_obj, end_date_obj


def apply_organization_filter(base_query, organization_id: str | None, model_class):
    """Apply organization filter to base query."""
    if organization_id:
        base_query = base_query.filter(model_class.organization_id == organization_id)
    return base_query


def apply_date_range_filter(base_query, start_date_obj: datetime, end_date_obj: datetime, model_class):
    """Apply date range filters to base query."""
    base_query = base_query.filter(model_class.created_at >= start_date_obj)
    base_query = base_query.filter(model_class.created_at <= end_date_obj)
    return base_query


def apply_user_filters(base_query, user_ids: List[str] | None, model_class):
    """Apply user ID filters to base query."""
    if user_ids:
        base_query = base_query.filter(model_class.user_id.in_(user_ids))
    return base_query


def build_pass_rate_stats(stats_dict: Dict[str, Dict[str, int]]) -> Dict[str, Dict[str, Any]]:
    """
    Build pass rate statistics from raw pass/fail counts.
    
    Args:
        stats_dict: Dictionary with structure {name: {"passed": count, "failed": count}}
        
    Returns:
        Dictionary with pass rates calculated: {name: {"total": int, "passed": int, "failed": int, "pass_rate": float}}
    """
    pass_rates = {}
    for name, stats in stats_dict.items():
        total = stats["passed"] + stats["failed"]
        pass_rate = round((stats["passed"] / total) * 100, 2) if total > 0 else 0
        pass_rates[name] = {
            "total": total,
            "passed": stats["passed"],
            "failed": stats["failed"],
            "pass_rate": pass_rate
        }
    return pass_rates


def build_response_data(mode: str, mode_definitions: Dict[str, List[str]], **data_sections) -> Dict[str, Any]:
    """
    Build response data based on mode, including metadata in all responses.
    
    Args:
        mode: The requested data mode
        mode_definitions: Dictionary mapping modes to required sections
        **data_sections: All available data sections
        
    Returns:
        Dictionary containing only the sections required for the specified mode
    """
    response = {"metadata": data_sections.get("metadata", {})}
    
    # Get the sections needed for this mode
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
    **additional_metadata
) -> Dict[str, Any]:
    """
    Build standard metadata structure for stats responses.
    
    Args:
        organization_id: Organization ID for filtering
        start_date_obj: Start date object
        end_date_obj: End date object  
        months: Number of months in the period
        mode: Data mode used
        total_items: Total number of items in the dataset
        **additional_metadata: Additional metadata fields specific to the stats type
        
    Returns:
        Dictionary containing standard metadata fields
    """
    metadata = {
        "generated_at": datetime.utcnow().isoformat(),
        "organization_id": organization_id,
        "period": f"Last {months} months",
        "start_date": start_date_obj.isoformat(),
        "end_date": end_date_obj.isoformat(),
        "total_items": total_items,
        "mode": mode,
    }
    
    # Add any additional metadata
    metadata.update(additional_metadata)
    
    return metadata


def apply_top_limit(stats_dict: Dict[str, int], top: int | None) -> Dict[str, int]:
    """
    Apply top limit to statistics dictionary, sorting by count descending.
    
    Args:
        stats_dict: Dictionary with structure {name: count}
        top: Optional limit for number of top items
        
    Returns:
        Dictionary limited to top N items, sorted by count descending
    """
    if not top:
        return stats_dict
    
    return dict(sorted(stats_dict.items(), key=lambda x: x[1], reverse=True)[:top])


def get_month_key(date_obj: datetime) -> str:
    """Get standardized month key from datetime object."""
    return date_obj.strftime("%Y-%m")


def safe_get_name(obj, fallback: str = "unknown") -> str:
    """Safely get name from an object, with fallback."""
    if obj and hasattr(obj, 'name') and obj.name:
        return obj.name
    return fallback


def safe_get_user_display_name(user_obj) -> str:
    """Get display name for user, preferring email, then username, then ID."""
    if not user_obj:
        return "unknown"
    
    if hasattr(user_obj, 'email') and user_obj.email:
        return user_obj.email
    elif hasattr(user_obj, 'username') and user_obj.username:
        return user_obj.username
    elif hasattr(user_obj, 'id'):
        return f"User {str(user_obj.id)[:8]}"
    else:
        return "unknown"


def initialize_monthly_stats_entry() -> Dict[str, Any]:
    """Initialize a standard monthly stats entry structure."""
    return {
        "total": 0,
        "statuses": {},
        "results": {"passed": 0, "failed": 0, "pending": 0}
    }


def infer_result_from_status(status_name: str) -> str:
    """
    Infer pass/fail/pending result from status name using flexible keyword matching.
    
    Args:
        status_name: The status name to analyze
        
    Returns:
        One of: "passed", "failed", "pending"
    """
    status_lower = status_name.lower()
    
    if any(keyword in status_lower for keyword in ['completed', 'finished', 'success', 'done']):
        return "passed"
    elif any(keyword in status_lower for keyword in ['failed', 'error', 'abort', 'cancel']):
        return "failed"
    else:
        return "pending"


def update_monthly_stats(monthly_stats: Dict[str, Dict], month_key: str, status_name: str, result: str):
    """
    Update monthly statistics with new data point.
    
    Args:
        monthly_stats: The monthly stats dictionary to update
        month_key: The month key (YYYY-MM format)
        status_name: The status name
        result: The inferred result (passed/failed/pending)
    """
    if month_key not in monthly_stats:
        monthly_stats[month_key] = initialize_monthly_stats_entry()
    
    monthly_stats[month_key]["total"] += 1
    
    # Update status breakdown
    if status_name not in monthly_stats[month_key]["statuses"]:
        monthly_stats[month_key]["statuses"][status_name] = 0
    monthly_stats[month_key]["statuses"][status_name] += 1
    
    # Update result breakdown
    monthly_stats[month_key]["results"][result] += 1


def build_empty_stats_response(
    mode: str,
    mode_definitions: Dict[str, List[str]],
    start_date_obj: datetime,
    end_date_obj: datetime,
    months: int,
    organization_id: str | None,
    **additional_metadata
) -> Dict[str, Any]:
    """
    Build empty stats response when no data is found.
    
    Args:
        mode: The requested data mode
        mode_definitions: Dictionary mapping modes to required sections
        start_date_obj: Start date object
        end_date_obj: End date object
        months: Number of months in the period
        organization_id: Organization ID
        **additional_metadata: Additional metadata fields
        
    Returns:
        Empty stats response respecting the requested mode
    """
    metadata = build_metadata(
        organization_id=organization_id,
        start_date_obj=start_date_obj,
        end_date_obj=end_date_obj,
        months=months,
        mode=mode,
        total_items=0,
        **additional_metadata
    )
    
    # Build empty data sections
    empty_data = {
        "metadata": metadata,
        # Common empty structures that can be used by different stats types
        "status_distribution": [],
        "result_distribution": {
            "total": 0,
            "passed": 0,
            "failed": 0,
            "pending": 0,
            "pass_rate": 0
        },
        "timeline": [],
        "overall_pass_rates": {
            "total": 0,
            "passed": 0,
            "failed": 0,
            "pass_rate": 0
        },
        "metric_pass_rates": {},
        "behavior_pass_rates": {},
        "category_pass_rates": {},
        "topic_pass_rates": {},
        "test_run_summary": [],
        "most_run_tests": [],
        "top_executors": [],
        "overall_summary": {
            "total_runs": 0,
            "unique_test_sets": 0,
            "unique_executors": 0,
            "most_common_status": "unknown",
            "pass_rate": 0
        }
    }
    
    return build_response_data(mode, mode_definitions, **empty_data)

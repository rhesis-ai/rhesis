"""Test result statistics functions with comprehensive filtering and mode-based data retrieval."""

from datetime import datetime, timedelta
from typing import Dict, List
from sqlalchemy.orm import Session


def get_test_result_stats(
    db: Session,
    organization_id: str | None = None,
    months: int = 6,
    test_run_id: str | None = None,  # Legacy single test run (backward compatibility)
    mode: str = "all",
    # Test-level filters
    test_set_ids: List[str] | None = None,
    behavior_ids: List[str] | None = None,
    category_ids: List[str] | None = None,
    topic_ids: List[str] | None = None,
    status_ids: List[str] | None = None,
    test_ids: List[str] | None = None,
    test_type_ids: List[str] | None = None,
    # Test run filters (new)
    test_run_ids: List[str] | None = None,  # Multiple test runs support
    # User-related filters
    user_ids: List[str] | None = None,
    assignee_ids: List[str] | None = None,
    owner_ids: List[str] | None = None,
    # Other filters
    prompt_ids: List[str] | None = None,
    priority_min: int | None = None,
    priority_max: int | None = None,
    tags: List[str] | None = None,
    # Date range filters
    start_date: str | None = None,
    end_date: str | None = None,
) -> Dict:
    """
    Get specialized statistics for test results with comprehensive filtering and configurable data modes.
    Analyzes test_metrics to determine pass/fail status per metric and overall.
    Designed for React charting libraries with performance optimization.
    
    Args:
        db: Database session
        organization_id: Optional organization ID for filtering
        months: Number of months to include in historical stats (used for timeline if no date range specified)
        test_run_id: Optional specific test run ID to filter by
        mode: Data mode to retrieve ('all', 'metrics', 'behavior', 'category', 'topic', 'overall', 'timeline', 'test_runs', 'summary')
        
        # Test-level filters
        test_set_ids: List of test set IDs to include
        behavior_ids: List of behavior IDs to include
        category_ids: List of category IDs to include  
        topic_ids: List of topic IDs to include
        status_ids: List of test status IDs to include
        test_ids: List of specific test IDs to include
        test_type_ids: List of test type IDs to include
        
        # User-related filters
        user_ids: List of user IDs (test creators) to include
        assignee_ids: List of assignee IDs to include
        owner_ids: List of test owner IDs to include
        
        # Other filters
        prompt_ids: List of prompt IDs to include
        priority_min: Minimum priority level (inclusive)
        priority_max: Maximum priority level (inclusive)
        tags: List of tags that tests must have
        
        # Date range filters (ISO format strings)
        start_date: Start date for filtering (overrides months parameter)
        end_date: End date for filtering (overrides months parameter)
        
    Returns:
        Dict containing requested data sections based on mode:
        - all: All data sections
        - metrics: metric_pass_rates only  
        - behavior: behavior_pass_rates only
        - category: category_pass_rates only
        - topic: topic_pass_rates only
        - overall: overall_pass_rates only
        - timeline: timeline data only
        - test_runs: test_run_summary only
        - summary: overall_pass_rates + metadata (lightweight)
    """
    from rhesis.backend.app import models
    from sqlalchemy import and_, case, distinct, func, extract
    from datetime import datetime, timedelta
    
    # Handle date range - custom dates override months parameter
    if start_date and end_date:
        start_date_obj = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        end_date_obj = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
    else:
        end_date_obj = datetime.utcnow()
        start_date_obj = end_date_obj - timedelta(days=30 * months)
    
    # Base query for test results with test_metrics, joining related entities
    base_query = (
        db.query(models.TestResult)
        .join(models.Test, models.TestResult.test_id == models.Test.id)
        .outerjoin(models.Behavior, models.Test.behavior_id == models.Behavior.id)
        .outerjoin(models.Category, models.Test.category_id == models.Category.id)
        .outerjoin(models.Topic, models.Test.topic_id == models.Topic.id)
        .outerjoin(models.TestRun, models.TestResult.test_run_id == models.TestRun.id)
    )
    
    # Apply all filters
    if organization_id:
        base_query = base_query.filter(models.TestResult.organization_id == organization_id)
    
    # Handle test run filtering (backward compatibility + new multiple support)
    combined_test_run_ids = []
    if test_run_id:
        combined_test_run_ids.append(test_run_id)
    if test_run_ids:
        combined_test_run_ids.extend(test_run_ids)
    
    if combined_test_run_ids:
        base_query = base_query.filter(models.TestResult.test_run_id.in_(combined_test_run_ids))
    
    # Date range filter
    base_query = base_query.filter(models.TestResult.created_at >= start_date_obj)
    base_query = base_query.filter(models.TestResult.created_at <= end_date_obj)
    
    # Test-level filters
    if test_set_ids:
        base_query = base_query.join(
            models.test_test_set_association,
            models.Test.id == models.test_test_set_association.c.test_id
        ).filter(models.test_test_set_association.c.test_set_id.in_(test_set_ids))
    
    if behavior_ids:
        base_query = base_query.filter(models.Test.behavior_id.in_(behavior_ids))
    
    if category_ids:
        base_query = base_query.filter(models.Test.category_id.in_(category_ids))
    
    if topic_ids:
        base_query = base_query.filter(models.Test.topic_id.in_(topic_ids))
    
    if status_ids:
        base_query = base_query.filter(models.Test.status_id.in_(status_ids))
    
    if test_ids:
        base_query = base_query.filter(models.Test.id.in_(test_ids))
    
    if test_type_ids:
        base_query = base_query.filter(models.Test.test_type_id.in_(test_type_ids))
    
    # User-related filters
    if user_ids:
        base_query = base_query.filter(models.Test.user_id.in_(user_ids))
    
    if assignee_ids:
        base_query = base_query.filter(models.Test.assignee_id.in_(assignee_ids))
    
    if owner_ids:
        base_query = base_query.filter(models.Test.owner_id.in_(owner_ids))
    
    # Other filters
    if prompt_ids:
        base_query = base_query.filter(models.Test.prompt_id.in_(prompt_ids))
    
    if priority_min is not None:
        base_query = base_query.filter(models.Test.priority >= priority_min)
    
    if priority_max is not None:
        base_query = base_query.filter(models.Test.priority <= priority_max)
    
    if tags:
        # Filter by tags using the relationship-based tag system
        from rhesis.backend.app.models.tag import TaggedItem, Tag
        base_query = base_query.join(
            TaggedItem, 
            and_(TaggedItem.entity_id == models.Test.id, TaggedItem.entity_type == 'Test')
        ).join(Tag, TaggedItem.tag_id == Tag.id).filter(Tag.name.in_(tags))
    
    # Get all test results with metrics and related entities
    test_results = base_query.all()
    
    if not test_results:
        return _empty_test_result_stats(start_date_obj, end_date_obj, months, organization_id, test_run_id, mode)
    
    # Parse metrics from all test results
    metric_stats = {}  # metric_name -> {passed: count, failed: count}
    overall_stats = {"passed": 0, "failed": 0}
    monthly_stats = {}  # "YYYY-MM" -> {overall: {passed, failed}, metrics: {metric_name: {passed, failed}}}
    test_run_stats = {}  # test_run_id -> stats
    
    # Dimensional breakdowns
    behavior_stats = {}  # behavior_name -> {passed: count, failed: count}
    category_stats = {}  # category_name -> {passed: count, failed: count}
    topic_stats = {}  # topic_name -> {passed: count, failed: count}
    
    for result in test_results:
        if not result.test_metrics or 'metrics' not in result.test_metrics:
            continue
            
        metrics = result.test_metrics['metrics']
        if not isinstance(metrics, dict):
            continue
        
        # Track metrics for this test result
        test_passed_overall = True
        test_metric_results = {}
        
        for metric_name, metric_data in metrics.items():
            if not isinstance(metric_data, dict) or 'is_successful' not in metric_data:
                continue
                
            is_successful = metric_data['is_successful']
            
            # Initialize metric stats if not exists
            if metric_name not in metric_stats:
                metric_stats[metric_name] = {"passed": 0, "failed": 0}
            
            # Update metric stats
            if is_successful:
                metric_stats[metric_name]["passed"] += 1
            else:
                metric_stats[metric_name]["failed"] += 1
                test_passed_overall = False
            
            test_metric_results[metric_name] = is_successful
        
        # Update overall stats
        if test_passed_overall:
            overall_stats["passed"] += 1
        else:
            overall_stats["failed"] += 1
        
        # Update dimensional stats (behavior, category, topic)
        # Behavior breakdown
        if result.test and result.test.behavior:
            behavior_name = result.test.behavior.name or "Unknown Behavior"
            if behavior_name not in behavior_stats:
                behavior_stats[behavior_name] = {"passed": 0, "failed": 0}
            if test_passed_overall:
                behavior_stats[behavior_name]["passed"] += 1
            else:
                behavior_stats[behavior_name]["failed"] += 1
        
        # Category breakdown  
        if result.test and result.test.category:
            category_name = result.test.category.name or "Unknown Category"
            if category_name not in category_stats:
                category_stats[category_name] = {"passed": 0, "failed": 0}
            if test_passed_overall:
                category_stats[category_name]["passed"] += 1
            else:
                category_stats[category_name]["failed"] += 1
        
        # Topic breakdown
        if result.test and result.test.topic:
            topic_name = result.test.topic.name or "Unknown Topic"
            if topic_name not in topic_stats:
                topic_stats[topic_name] = {"passed": 0, "failed": 0}
            if test_passed_overall:
                topic_stats[topic_name]["passed"] += 1
            else:
                topic_stats[topic_name]["failed"] += 1
        
        # Update monthly stats
        if result.created_at:
            month_key = result.created_at.strftime("%Y-%m")
            if month_key not in monthly_stats:
                monthly_stats[month_key] = {
                    "overall": {"passed": 0, "failed": 0},
                    "metrics": {}
                }
            
            # Update monthly overall stats
            if test_passed_overall:
                monthly_stats[month_key]["overall"]["passed"] += 1
            else:
                monthly_stats[month_key]["overall"]["failed"] += 1
            
            # Update monthly metric stats
            for metric_name, is_successful in test_metric_results.items():
                if metric_name not in monthly_stats[month_key]["metrics"]:
                    monthly_stats[month_key]["metrics"][metric_name] = {"passed": 0, "failed": 0}
                
                if is_successful:
                    monthly_stats[month_key]["metrics"][metric_name]["passed"] += 1
                else:
                    monthly_stats[month_key]["metrics"][metric_name]["failed"] += 1
        
        # Update test run stats
        if result.test_run_id:
            run_key = str(result.test_run_id)
            if run_key not in test_run_stats:
                # Get test run info
                test_run = db.query(models.TestRun).filter_by(id=result.test_run_id).first()
                test_run_stats[run_key] = {
                    "id": run_key,
                    "name": test_run.name if test_run and test_run.name else f"Test Run {run_key[:8]}",
                    "created_at": test_run.created_at.isoformat() if test_run and test_run.created_at else None,
                    "overall": {"passed": 0, "failed": 0},
                    "metrics": {},
                    "total_tests": 0
                }
            
            test_run_stats[run_key]["total_tests"] += 1
            
            # Update test run overall stats
            if test_passed_overall:
                test_run_stats[run_key]["overall"]["passed"] += 1
            else:
                test_run_stats[run_key]["overall"]["failed"] += 1
            
            # Update test run metric stats
            for metric_name, is_successful in test_metric_results.items():
                if metric_name not in test_run_stats[run_key]["metrics"]:
                    test_run_stats[run_key]["metrics"][metric_name] = {"passed": 0, "failed": 0}
                
                if is_successful:
                    test_run_stats[run_key]["metrics"][metric_name]["passed"] += 1
                else:
                    test_run_stats[run_key]["metrics"][metric_name]["failed"] += 1
    
    # Build metric pass rates
    metric_pass_rates = {}
    for metric_name, stats in metric_stats.items():
        total = stats["passed"] + stats["failed"]
        pass_rate = round((stats["passed"] / total) * 100, 2) if total > 0 else 0
        metric_pass_rates[metric_name] = {
            "total": total,
            "passed": stats["passed"],
            "failed": stats["failed"],
            "pass_rate": pass_rate
        }
    
    # Build overall pass rates
    total_tests = overall_stats["passed"] + overall_stats["failed"]
    overall_pass_rate = round((overall_stats["passed"] / total_tests) * 100, 2) if total_tests > 0 else 0
    overall_pass_rates = {
        "total": total_tests,
        "passed": overall_stats["passed"],
        "failed": overall_stats["failed"],
        "pass_rate": overall_pass_rate
    }
    
    # Build dimensional pass rates
    def build_dimensional_rates(dimension_stats):
        dimensional_rates = {}
        for name, stats in dimension_stats.items():
            total = stats["passed"] + stats["failed"]
            pass_rate = round((stats["passed"] / total) * 100, 2) if total > 0 else 0
            dimensional_rates[name] = {
                "total": total,
                "passed": stats["passed"],
                "failed": stats["failed"],
                "pass_rate": pass_rate
            }
        return dimensional_rates
    
    behavior_pass_rates = build_dimensional_rates(behavior_stats)
    category_pass_rates = build_dimensional_rates(category_stats)
    topic_pass_rates = build_dimensional_rates(topic_stats)
    
    # Build timeline data
    timeline = []
    for month_key in sorted(monthly_stats.keys()):
        month_data = monthly_stats[month_key]
        overall_total = month_data["overall"]["passed"] + month_data["overall"]["failed"]
        overall_pass_rate = round((month_data["overall"]["passed"] / overall_total) * 100, 2) if overall_total > 0 else 0
        
        # Build metric breakdown for this month
        metric_breakdown = {}
        for metric_name, metric_data in month_data["metrics"].items():
            metric_total = metric_data["passed"] + metric_data["failed"]
            metric_pass_rate = round((metric_data["passed"] / metric_total) * 100, 2) if metric_total > 0 else 0
            metric_breakdown[metric_name] = {
                "total": metric_total,
                "passed": metric_data["passed"],
                "failed": metric_data["failed"],
                "pass_rate": metric_pass_rate
            }
        
        timeline.append({
            "date": month_key,
            "overall": {
                "total": overall_total,
                "passed": month_data["overall"]["passed"],
                "failed": month_data["overall"]["failed"],
                "pass_rate": overall_pass_rate
            },
            "metrics": metric_breakdown
        })
    
    # Build test run summary
    test_run_summary = []
    for run_data in test_run_stats.values():
        # Calculate overall pass rate for this run
        run_total = run_data["overall"]["passed"] + run_data["overall"]["failed"]
        run_pass_rate = round((run_data["overall"]["passed"] / run_total) * 100, 2) if run_total > 0 else 0
        
        # Calculate metric pass rates for this run
        run_metric_breakdown = {}
        for metric_name, metric_data in run_data["metrics"].items():
            metric_total = metric_data["passed"] + metric_data["failed"]
            metric_pass_rate = round((metric_data["passed"] / metric_total) * 100, 2) if metric_total > 0 else 0
            run_metric_breakdown[metric_name] = {
                "total": metric_total,
                "passed": metric_data["passed"],
                "failed": metric_data["failed"],
                "pass_rate": metric_pass_rate
            }
        
        test_run_summary.append({
            "id": run_data["id"],
            "name": run_data["name"],
            "created_at": run_data["created_at"],
            "total_tests": run_data["total_tests"],
            "overall": {
                "total": run_total,
                "passed": run_data["overall"]["passed"],
                "failed": run_data["overall"]["failed"],
                "pass_rate": run_pass_rate
            },
            "metrics": run_metric_breakdown
        })
    
    # Sort test runs by creation date (newest first)
    test_run_summary.sort(key=lambda x: x["created_at"] or "", reverse=True)
    
    # Build metadata
    metadata = {
        "generated_at": datetime.utcnow().isoformat(),
        "organization_id": organization_id,
        "test_run_id": test_run_id,
        "period": f"Last {months} months",
        "start_date": start_date_obj.isoformat(),
        "end_date": end_date_obj.isoformat(),
        "total_test_runs": len(test_run_stats),
        "total_test_results": total_tests,
        "mode": mode,
        "available_metrics": list(metric_stats.keys()),
        "available_behaviors": list(behavior_stats.keys()),
        "available_categories": list(category_stats.keys()),
        "available_topics": list(topic_stats.keys())
    }
    
    # Return data based on mode
    if mode == "all":
        return {
            "metric_pass_rates": metric_pass_rates,
            "behavior_pass_rates": behavior_pass_rates,
            "category_pass_rates": category_pass_rates,
            "topic_pass_rates": topic_pass_rates,
            "overall_pass_rates": overall_pass_rates,
            "timeline": timeline,
            "test_run_summary": test_run_summary,
            "metadata": metadata
        }
    elif mode == "metrics":
        return {
            "metric_pass_rates": metric_pass_rates,
            "metadata": metadata
        }
    elif mode == "behavior":
        return {
            "behavior_pass_rates": behavior_pass_rates,
            "metadata": metadata
        }
    elif mode == "category":
        return {
            "category_pass_rates": category_pass_rates,
            "metadata": metadata
        }
    elif mode == "topic":
        return {
            "topic_pass_rates": topic_pass_rates,
            "metadata": metadata
        }
    elif mode == "overall":
        return {
            "overall_pass_rates": overall_pass_rates,
            "metadata": metadata
        }
    elif mode == "timeline":
        return {
            "timeline": timeline,
            "metadata": metadata
        }
    elif mode == "test_runs":
        return {
            "test_run_summary": test_run_summary,
            "metadata": metadata
        }
    elif mode == "summary":
        # Lightweight overview - just overall stats + metadata
        return {
            "overall_pass_rates": overall_pass_rates,
            "metadata": metadata
        }
    else:
        # Default to all if unknown mode
        return {
            "metric_pass_rates": metric_pass_rates,
            "behavior_pass_rates": behavior_pass_rates,
            "category_pass_rates": category_pass_rates,
            "topic_pass_rates": topic_pass_rates,
            "overall_pass_rates": overall_pass_rates,
            "timeline": timeline,
            "test_run_summary": test_run_summary,
            "metadata": metadata
        }


def _empty_test_result_stats(start_date, end_date, months, organization_id, test_run_id, mode="all"):
    """Return empty stats structure when no test results found, respecting mode"""
    from datetime import datetime
    
    metadata = {
        "generated_at": datetime.utcnow().isoformat(),
        "organization_id": organization_id,
        "test_run_id": test_run_id,
        "period": f"Last {months} months",
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "total_test_runs": 0,
        "total_test_results": 0,
        "mode": mode,
        "available_metrics": [],
        "available_behaviors": [],
        "available_categories": [],
        "available_topics": []
    }
    
    empty_overall = {
        "total": 0,
        "passed": 0,
        "failed": 0,
        "pass_rate": 0
    }
    
    # Return data based on mode
    if mode == "all":
        return {
            "metric_pass_rates": {},
            "behavior_pass_rates": {},
            "category_pass_rates": {},
            "topic_pass_rates": {},
            "overall_pass_rates": empty_overall,
            "timeline": [],
            "test_run_summary": [],
            "metadata": metadata
        }
    elif mode == "metrics":
        return {
            "metric_pass_rates": {},
            "metadata": metadata
        }
    elif mode == "behavior":
        return {
            "behavior_pass_rates": {},
            "metadata": metadata
        }
    elif mode == "category":
        return {
            "category_pass_rates": {},
            "metadata": metadata
        }
    elif mode == "topic":
        return {
            "topic_pass_rates": {},
            "metadata": metadata
        }
    elif mode == "overall" or mode == "summary":
        return {
            "overall_pass_rates": empty_overall,
            "metadata": metadata
        }
    elif mode == "timeline":
        return {
            "timeline": [],
            "metadata": metadata
        }
    elif mode == "test_runs":
        return {
            "test_run_summary": [],
            "metadata": metadata
        }
    else:
        # Default to all if unknown mode
        return {
            "metric_pass_rates": {},
            "behavior_pass_rates": {},
            "category_pass_rates": {},
            "topic_pass_rates": {},
            "overall_pass_rates": empty_overall,
            "timeline": [],
            "test_run_summary": [],
            "metadata": metadata
        }
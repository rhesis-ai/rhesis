"""Shared utility functions for native judge metrics.

This module contains utility functions that are identical across both
single-turn (JudgeBase) and conversational (ConversationalJudge) metrics.
"""

import logging
import traceback
from pathlib import Path
from typing import Any, Dict

from jinja2 import Environment, FileSystemLoader, select_autoescape

from rhesis.sdk.metrics.base import MetricResult, ScoreType


def get_base_details(
    score_type: ScoreType, prompt: str, metric_name: str = None
) -> Dict[str, Any]:
    """
    Get base details dictionary common to all metric types.

    Args:
        score_type: The score type of the metric
        prompt: The evaluation prompt
        metric_name: Optional name of the metric

    Returns:
        Dict[str, Any]: Base details dictionary

    Raises:
        ValueError: If score_type is None
    """
    if score_type is None:
        raise ValueError("score_type must be set before calling get_base_details")

    score_type_value = score_type.value if isinstance(score_type, ScoreType) else str(score_type)
    details = {
        "score_type": score_type_value,
        "prompt": prompt,
    }
    
    if metric_name:
        details["name"] = metric_name
    
    return details


def handle_evaluation_error(
    e: Exception,
    metric_name: str,
    model: Any,
    details: Dict[str, Any],
    default_score: Any,
) -> MetricResult:
    """
    Handle evaluation errors with consistent logging and error details.

    Args:
        e: The exception that occurred
        metric_name: Name of the metric
        model: The model being used
        details: Details dictionary to update
        default_score: Default score to return on error

    Returns:
        MetricResult: Error result with default score
    """
    logger = logging.getLogger(__name__)
    error_msg = f"Error evaluating with {metric_name}: {str(e)}"

    logger.error(f"Exception in metric evaluation: {error_msg}")
    logger.error(f"Exception type: {type(e).__name__}")
    logger.error(f"Exception details: {str(e)}")
    logger.error(f"Full traceback:\n{traceback.format_exc()}")

    # Update details with error-specific fields
    details.update(
        {
            "error": error_msg,
            "reason": error_msg,
            "exception_type": type(e).__name__,
            "exception_details": str(e),
            "model": model,
            "is_successful": False,
        }
    )

    return MetricResult(score=default_score, details=details)


def setup_jinja_environment(templates_dir_path: Path) -> Environment:
    """
    Set up Jinja environment for template rendering.

    This function initializes a Jinja2 environment with the templates directory
    and configures it for optimal template rendering performance.

    Args:
        templates_dir_path: Path to the templates directory

    Returns:
        Environment: Configured Jinja2 environment
    """
    return Environment(
        loader=FileSystemLoader(templates_dir_path),
        autoescape=select_autoescape(["html", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )

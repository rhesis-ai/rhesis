"""
Utility functions for managing behavior metrics.

Note: Metric model to config conversion is now handled directly by the 
MetricEvaluator class - no intermediate conversion needed.
"""

from typing import List
from uuid import UUID

from sqlalchemy.orm import Session

from rhesis.backend.app.models.metric import Metric
from rhesis.backend.logging.rhesis_logger import logger


def get_behavior_metrics(db: Session, behavior_id: UUID) -> List[Metric]:
    """
    Retrieve metrics associated with a behavior.

    Args:
        db: Database session
        behavior_id: UUID of the behavior

    Returns:
        List of Metric model instances (evaluator handles conversion)
    """
    if not behavior_id:
        logger.warning("No behavior ID provided for metrics retrieval")
        return []

    try:
        # Query metrics related to the behavior
        metrics = (
            db.query(Metric)
            .join(Metric.behaviors)
            .filter(Metric.behaviors.any(id=behavior_id))
            .all()
        )

        # Filter out metrics without class_name
        valid_metrics = [m for m in metrics if m.class_name]
        
        if len(valid_metrics) < len(metrics):
            logger.warning(f"Filtered out {len(metrics) - len(valid_metrics)} metrics without class_name")

        return valid_metrics

    except Exception as e:
        logger.error(
            f"Error retrieving metrics for behavior {behavior_id}: {str(e)}", exc_info=True
        )
        return []

"""
Utility functions for managing requirement metrics.

Note: Metric model to config conversion is now handled directly by the
MetricEvaluator class - no intermediate conversion needed.
"""

import logging
from typing import List
from uuid import UUID

from sqlalchemy.orm import Session

from rhesis.backend.app.models.metric import Metric

logger = logging.getLogger(__name__)


def get_requirement_metrics(db: Session, requirement_id: UUID) -> List[Metric]:
    """
    Retrieve metrics associated with a requirement.

    Args:
        db: Database session
        requirement_id: UUID of the requirement

    Returns:
        List of Metric model instances (evaluator handles conversion)
    """
    if not requirement_id:
        logger.warning("No requirement ID provided for metrics retrieval")
        return []

    try:
        # Query metrics related to the requirement
        metrics = (
            db.query(Metric)
            .join(Metric.requirements)
            .filter(Metric.requirements.any(id=requirement_id))
            .all()
        )

        # Filter out metrics without class_name
        valid_metrics = [m for m in metrics if m.class_name]

        if len(valid_metrics) < len(metrics):
            logger.warning(
                f"Filtered out {len(metrics) - len(valid_metrics)} metrics without class_name"
            )

        return valid_metrics

    except Exception as e:
        logger.error(
            f"Error retrieving metrics for requirement {requirement_id}: {str(e)}", exc_info=True
        )
        return []

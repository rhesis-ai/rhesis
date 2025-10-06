"""Test statistics functions for comprehensive test entity analysis."""

from typing import Dict

from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.services.stats import StatsCalculator


def get_test_stats(
    db: Session,
    current_user_organization_id: str | None,
    top: int | None = None,
    months: int = 6,
) -> Dict:
    """
    Get comprehensive statistics about tests.

    Args:
        db: Database session
        current_user_organization_id: Optional organization ID for filtering
        top: Optional number of top items to show per dimension
        months: Number of months to include in historical stats (default: 6)

    Returns:
        Dict containing:
        - total: Total number of tests
        - stats: Breakdown by dimensions (status, topic, behavior, category, etc.)
        - history: Historical trend data (monthly counts)
        - metadata: Generation timestamp, organization_id, entity_type
    """
    calculator = StatsCalculator(db, organization_id=current_user_organization_id)
    return calculator.get_entity_stats(
        entity_model=models.Test,
        organization_id=current_user_organization_id,
        top=top,
        months=months,
    )


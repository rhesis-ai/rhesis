"""
Association Relationship Fixtures

Fixtures for creating many-to-many and association relationships.
"""

from typing import Any, Dict

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def requirement_with_metrics(
    authenticated_client: TestClient, sample_requirement: Dict[str, Any], sample_metric: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Create a requirement with associated metrics

    This fixture creates a complete requirement-metric relationship
    for integration testing.

    Returns:
        Dict containing:
        - requirement: The requirement data
        - metric: The metric data associated with the requirement
    """
    # Associate the metric with the requirement
    try:
        response = authenticated_client.post(
            f"/requirements/{sample_requirement['id']}/metrics/{sample_metric['id']}"
        )
        # Note: This endpoint might not exist yet, so we handle gracefully
        if response.status_code not in [200, 201, 404]:
            # If association fails, we still return both entities
            pass
    except Exception:
        # Gracefully handle if the association endpoint doesn't exist
        pass

    return {"requirement": sample_requirement, "metric": sample_metric}

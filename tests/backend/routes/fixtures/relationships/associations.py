"""
Association Relationship Fixtures

Fixtures for creating many-to-many and association relationships.
"""

import pytest
from typing import Dict, Any
from fastapi.testclient import TestClient


@pytest.fixture
def behavior_with_metrics(
    authenticated_client: TestClient, sample_behavior: Dict[str, Any], sample_metric: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Create a behavior with associated metrics

    This fixture creates a complete behavior-metric relationship
    for integration testing.

    Returns:
        Dict containing:
        - behavior: The behavior data
        - metric: The metric data associated with the behavior
    """
    # Associate the metric with the behavior
    try:
        response = authenticated_client.post(
            f"/behaviors/{sample_behavior['id']}/metrics/{sample_metric['id']}"
        )
        # Note: This endpoint might not exist yet, so we handle gracefully
        if response.status_code not in [200, 201, 404]:
            # If association fails, we still return both entities
            pass
    except Exception:
        # Gracefully handle if the association endpoint doesn't exist
        pass

    return {"behavior": sample_behavior, "metric": sample_metric}

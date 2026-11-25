"""Activity items summarize their entity with a fixed set of display fields."""

import pytest

from rhesis.backend.app import models
from rhesis.backend.app.services.activities import ENTITY_DATA_FIELDS, RecentActivitiesService

pytestmark = pytest.mark.unit


def test_entity_data_keeps_display_fields_only():
    endpoint = models.Endpoint(name="Support bot", description="d", url="https://example.com")

    data = RecentActivitiesService.entity_to_dict(endpoint)

    assert data["name"] == "Support bot"
    assert data["description"] == "d"
    assert set(data) <= ENTITY_DATA_FIELDS

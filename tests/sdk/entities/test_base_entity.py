import os
from unittest.mock import patch

from rhesis.sdk.entities.base_entity import BaseEntity

os.environ["RHESIS_API_KEY"] = "test_api_key"
os.environ["RHESIS_BASE_URL"] = "http://test:8000"


class TestEntity(BaseEntity):
    endpoint = "test"


@patch("requests.api.request")
def test_delete(mock_request):
    record_id = 1
    entity = TestEntity()
    entity.delete(record_id)
    mock_request.assert_called_once_with(
        "delete",
        "http://test:8000/test/1/",
        headers={
            "Authorization": "Bearer test_api_key",
            "Content-Type": "application/json",
        },
    )

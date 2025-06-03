import pytest
from rhesis.sdk.entities import Status


@pytest.fixture
def test_status():
    """Fixture that creates and returns a test status"""
    # Test data for status
    test_data = {"name": "Test Status", "description": "This is a test status"}

    # Try to find existing test status
    statuses = Status.all()
    test_status = next((s for s in statuses if s["name"] == test_data["name"]), None)

    if test_status:
        return test_status

    # Create new test status if it doesn't exist
    status = Status(**test_data).save()

    # Verify the save was successful
    assert status is not None, "Failed to create test status"
    assert "id" in status, "Created status missing ID"

    return status

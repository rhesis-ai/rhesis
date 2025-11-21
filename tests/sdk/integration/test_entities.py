import pytest
from requests import HTTPError

from rhesis.sdk.entities.behavior import Behavior


def test_behavior(db_cleanup):
    behavior = Behavior(
        name="Test Behavior",
        description="Test Description",
    )

    result = behavior.push()

    assert result["id"] is not None
    assert result["name"] == "Test Behavior"
    assert result["description"] == "Test Description"


def test_behavior_push_pull(db_cleanup):
    behavior = Behavior(
        name="Test push pull behavior",
        description="Test push pull behavior description",
    )
    behavior.push()

    pulled_behavior = behavior.pull()

    assert pulled_behavior.name == "Test push pull behavior"
    assert pulled_behavior.description == "Test push pull behavior description"


def test_behavior_delete(db_cleanup):
    behavior = Behavior(
        name="Test push pull behavior",
        description="Test push pull behavior description",
    )

    behavior.push()
    behavior.delete()

    with pytest.raises(HTTPError):
        behavior.pull()

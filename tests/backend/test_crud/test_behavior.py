import pytest
from rhesis.app.schemas import BehaviorCreate, BehaviorUpdate
from rhesis.tests.mock import generate_mock_data  # Import the mock data generator


@pytest.fixture
def test_behavior_data():
    return generate_mock_data(BehaviorCreate)

@pytest.fixture
def test_behavior(client, test_behavior_data):

    response = client.post(
        "/behaviors/",
        json=test_behavior_data,
    )

    return response.json()

def test_create_behavior(client, test_behavior_data):

    response = client.post(
        "/behaviors/",
        json=test_behavior_data,
    )
    assert response.status_code == 200
    assert response.json()["name"] == test_behavior_data["name"]


def test_read_behaviors(client):
    response = client.get("/behaviors/")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0


def test_read_behavior(client, test_behavior):

    # Read the created behavior
    behavior_id = test_behavior["id"]
    response = client.get(f"/behaviors/{behavior_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == test_behavior["name"]


def test_update_behavior(client, test_behavior):

    # Update the behavior
    behavior_id = test_behavior["id"]

    behavior_data_update = generate_mock_data(BehaviorUpdate)
    behavior_data_update = {
        key: value for key, value in behavior_data_update.items() if value is not None
    }

    response = client.put(
        f"/behaviors/{behavior_id}",
        json=behavior_data_update,
    )

    # Now, check if the behavior is updated
    assert response.status_code == 200

    for key, value in behavior_data_update.items():
        assert response.json()[key] == value

def test_delete_behavior(client, test_behavior):

    # Delete the created behavior
    behavior_id = test_behavior["id"]

    response = client.delete(f"/behaviors/{behavior_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == test_behavior["name"]




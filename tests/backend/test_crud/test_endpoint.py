import pytest
from rhesis.app.schemas import EndpointCreate, EndpointUpdate
from rhesis.tests.mock import generate_mock_data  # Import the mock data generator


@pytest.fixture
def test_endpoint_data():
    return generate_mock_data(EndpointCreate)

@pytest.fixture
def test_endpoint(client, test_endpoint_data):

    response = client.post(
        "/endpoints/",
        json=test_endpoint_data,
    )

    return response.json()

def test_create_endpoint(client, test_endpoint_data):

    response = client.post(
        "/endpoints/",
        json=test_endpoint_data,
    )
    assert response.status_code == 200
    assert response.json()["name"] == test_endpoint_data["name"]


def test_read_endpoints(client):
    response = client.get("/endpoints/")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0


def test_read_endpoint(client, test_endpoint):

    # Read the created endpoint
    endpoint_id = test_endpoint["id"]
    response = client.get(f"/endpoints/{endpoint_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == test_endpoint["name"]


def test_update_endpoint(client, test_endpoint):

    # Update the endpoint
    endpoint_id = test_endpoint["id"]

    endpoint_data_update = generate_mock_data(EndpointUpdate)
    endpoint_data_update = {
        key: value for key, value in endpoint_data_update.items() if value is not None
    }

    response = client.put(
        f"/endpoints/{endpoint_id}",
        json=endpoint_data_update,
    )

    # Now, check if the endpoint is updated
    assert response.status_code == 200

    for key, value in endpoint_data_update.items():
        assert response.json()[key] == value

def test_delete_endpoint(client, test_endpoint):

    # Delete the created endpoint
    endpoint_id = test_endpoint["id"]

    response = client.delete(f"/endpoints/{endpoint_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == test_endpoint["name"]




import pytest
from rhesis.app.schemas import CategoryCreate, CategoryUpdate
from rhesis.tests.mock import generate_mock_data  # Import the mock data generator


@pytest.fixture
def test_category_data():
    return generate_mock_data(CategoryCreate)

@pytest.fixture
def test_category(client, test_category_data):

    response = client.post(
        "/categories/",
        json=test_category_data,
    )

    return response.json()

def test_create_category(client, test_category_data):

    response = client.post(
        "/categories/",
        json=test_category_data,
    )
    assert response.status_code == 200
    assert response.json()["name"] == test_category_data["name"]


def test_read_categories(client):
    response = client.get("/categories/")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0


def test_read_category(client, test_category):

    # Read the created category
    category_id = test_category["id"]
    response = client.get(f"/categories/{category_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == test_category["name"]


def test_update_category(client, test_category):

    # Update the category
    category_id = test_category["id"]

    category_data_update = generate_mock_data(CategoryUpdate)
    category_data_update = {
        key: value for key, value in category_data_update.items() if value is not None
    }

    response = client.put(
        f"/categories/{category_id}",
        json=category_data_update,
    )

    # Now, check if the category is updated
    assert response.status_code == 200

    for key, value in category_data_update.items():
        assert response.json()[key] == value

def test_delete_category(client, test_category):

    # Delete the created category
    category_id = test_category["id"]

    response = client.delete(f"/categories/{category_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == test_category["name"]




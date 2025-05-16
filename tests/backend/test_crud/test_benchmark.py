import pytest
from rhesis.app.schemas import BenchmarkCreate, BenchmarkUpdate
from rhesis.tests.mock import generate_mock_data  # Import the mock data generator


@pytest.fixture
def test_benchmark_data():
    return generate_mock_data(BenchmarkCreate)

@pytest.fixture
def test_benchmark(client, test_benchmark_data):

    response = client.post(
        "/benchmarks/",
        json=test_benchmark_data,
    )

    return response.json()

def test_create_benchmark(client, test_benchmark_data):

    response = client.post(
        "/benchmarks/",
        json=test_benchmark_data,
    )
    assert response.status_code == 200
    assert response.json()["name"] == test_benchmark_data["name"]


def test_read_benchmarks(client):
    response = client.get("/benchmarks/")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0


def test_read_benchmark(client, test_benchmark):

    # Read the created benchmark
    benchmark_id = test_benchmark["id"]
    response = client.get(f"/benchmarks/{benchmark_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == test_benchmark["name"]


def test_update_benchmark(client, test_benchmark):

    # Update the benchmark
    benchmark_id = test_benchmark["id"]

    benchmark_data_update = generate_mock_data(BenchmarkUpdate)
    benchmark_data_update = {
        key: value for key, value in benchmark_data_update.items() if value is not None
    }

    response = client.put(
        f"/benchmarks/{benchmark_id}",
        json=benchmark_data_update,
    )

    # Now, check if the benchmark is updated
    assert response.status_code == 200

    for key, value in benchmark_data_update.items():
        assert response.json()[key] == value

def test_delete_benchmark(client, test_benchmark):

    # Delete the created benchmark
    benchmark_id = test_benchmark["id"]

    response = client.delete(f"/benchmarks/{benchmark_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == test_benchmark["name"]




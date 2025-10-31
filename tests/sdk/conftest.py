import subprocess
import time
from pathlib import Path
from typing import Generator

import pytest
import requests


@pytest.fixture(scope="session")
def docker_compose_test_env() -> Generator[dict, None, None]:
    """
    🐳 Start docker-compose test environment for integration tests.

    This fixture:
    - Starts postgres + backend from docker-compose.test.yml
    - Waits for services to be healthy
    - Yields connection info
    - Tears down after all tests complete
    """
    compose_file = Path("../../docker-compose.test.yml")

    # Clean up any existing containers
    subprocess.run(["docker", "compose", "-f", compose_file, "down", "-v"], capture_output=True)

    # Start services
    result = subprocess.run(
        ["docker", "compose", "-f", compose_file, "up", "-d"],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        pytest.fail(f"Failed to start docker-compose: {result.stderr}")

    # Wait for backend to be healthy
    print("Waiting for backend to be ready...")
    max_attempts = 60
    backend_url = "http://localhost:8080/health"

    for attempt in range(max_attempts):
        try:
            response = requests.get(backend_url, timeout=2)
            if response.status_code == 200:
                print(f"✅ Backend is ready! (attempt {attempt + 1}/{max_attempts})")
                break
        except requests.exceptions.RequestException:
            pass
        time.sleep(1)

        if attempt == max_attempts - 1:
            pytest.fail(f"Backend failed to start within {max_attempts} seconds\n\n")

    # Yield test environment info
    yield {
        "base_url": "http://localhost:8080",
        "api_key": "rh-test-token",
    }

    # Teardown
    print("Tearing down docker-compose test environment...")
    subprocess.run(["docker", "compose", "-f", compose_file, "down", "-v"], capture_output=True)


@pytest.fixture
def integration_client(docker_compose_test_env):
    """
    🔌 Configured Rhesis SDK client for integration tests.
    """
    api_key = docker_compose_test_env["api_key"]
    base_url = docker_compose_test_env["base_url"]

    from rhesis.sdk.client import Client

    return Client(api_key=api_key, base_url=base_url)

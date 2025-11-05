import subprocess
import time
from pathlib import Path
from typing import Generator

import pytest
import requests


@pytest.fixture(scope="session")
def docker_compose_test_env() -> Generator[dict, None, None]:
    compose_file = Path(__file__).parent / "docker-compose.test.yml"
    # Test if backend is running
    max_attempts = 3
    backend_url = "http://localhost:8080/health"
    backend_is_running = False

    print("🔄 Checking if backend is running...")

    for attempt in range(max_attempts):
        try:
            response = requests.get(backend_url, timeout=2)
            if response.status_code == 200:
                backend_is_running = True
                break
        except requests.exceptions.RequestException:
            backend_is_running = False
            time.sleep(1)

    # Start services
    if not backend_is_running:
        print("🔄 Backend is not running, starting backend...")
        result = subprocess.run(
            ["docker", "compose", "-f", compose_file, "up", "-d", "--build"],
            text=True,
        )

        if result.returncode != 0:
            pytest.fail("Failed to start docker-compose")
    else:
        print("🟢 Backend is already running, skipping startup...")

    # Wait for backend to be healthy
    print("🔄 Waiting for backend to be ready...")
    max_attempts = 60

    for attempt in range(max_attempts):
        print(f"Backend check - attempt {attempt + 1}/{max_attempts}")
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


@pytest.fixture(scope="function")
def db_cleanup(docker_compose_test_env):
    """
    Automatic database cleanup for integration tests.
    Runs automatically before and after EACH test in tests/sdk/.
    """
    from sqlalchemy import create_engine, text

    db_url = "postgresql://rhesis-user:your-secured-password@localhost:5432/rhesis-db"
    engine = create_engine(db_url)

    # 🧼 Cleanup at START (before test runs)
    try:
        with engine.connect() as conn:
            conn.execute(text("TRUNCATE TABLE metric CASCADE;"))
            conn.commit()
    except Exception as e:
        print(f"⚠️  Warning: Could not clean database at start: {e}")

    yield  # Test runs here

    # 🧹 Cleanup at END (after test completes)
    print("🔄 Cleaning database after test...")
    try:
        with engine.connect() as conn:
            conn.execute(text("TRUNCATE TABLE metric CASCADE;"))
            conn.commit()
    except Exception as e:
        print(f"⚠️  Warning: Could not clean database at end: {e}")

    engine.dispose()

import subprocess
import time
from pathlib import Path
from typing import Generator

import psycopg2
import pytest
import requests

# ANSI color codes
BLUE = "\033[0;34m"
GREEN = "\033[0;32m"
RED = "\033[0;31m"
CYAN = "\033[0;36m"
NC = "\033[0m"  # No Color

DATABASE_PORT = 10000
BACKEND_PORT = 10001

# Quick Start mode provides these defaults automatically:
# - Organization: "Local Org"
# - User: admin@local.dev
# - API Token: rh-local-token
QUICK_START_TOKEN = "rh-local-token"


@pytest.fixture(autouse=True)
def set_api_keys(monkeypatch):
    """Override parent conftest to use integration test backend URL."""
    monkeypatch.setenv("RHESIS_API_KEY", QUICK_START_TOKEN)
    monkeypatch.setenv("RHESIS_BASE_URL", f"http://localhost:{BACKEND_PORT}")


@pytest.fixture(scope="session", autouse=True)
def docker_compose_test_env() -> Generator[dict, None, None]:
    """
    Set up isolated docker-compose environment for integration tests.

    Uses Quick Start mode which automatically creates:
    - Default organization "Local Org"
    - Default admin user admin@local.dev
    - Default API token rh-local-token
    - Initial seed data (example project, tests, etc.)
    """
    print(f"{BLUE}🐳 Starting isolated docker-compose environment (Quick Start mode){NC}")
    compose_file = Path(__file__).parent / "docker-compose.yml"

    # Test if backend is running
    max_attempts = 3
    backend_url = f"http://localhost:{BACKEND_PORT}/health"
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
            ["docker", "compose", "-f", compose_file, "up", "--detach", "--build"],
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

    # Display Quick Start info
    print()
    print(f"{GREEN}════════════════════════════════════════════════{NC}")
    print(f"{GREEN}✅ Quick Start Mode Active{NC}")
    print(f"{GREEN}════════════════════════════════════════════════{NC}")
    print(f"{CYAN}Organization: Local Org{NC}")
    print(f"{CYAN}User:         admin@local.dev{NC}")
    print(f"{CYAN}API Token:    {QUICK_START_TOKEN}{NC}")
    print(f"{GREEN}════════════════════════════════════════════════{NC}")
    print()

    # Yield test environment info
    test_config = {
        "base_url": f"http://localhost:{BACKEND_PORT}",
        "api_key": QUICK_START_TOKEN,
    }

    yield test_config


def _get_db_connection():
    """Get a database connection for test cleanup."""
    return psycopg2.connect(
        host="localhost",
        database="rhesis-db",
        user="rhesis-user",
        password="your-secured-password",
        port=DATABASE_PORT,
    )


def _truncate_test_tables(conn) -> None:
    """Truncate tables that tests create data in."""
    conn.autocommit = True
    cur = conn.cursor()
    # Only truncate tables that tests directly create data in
    # Don't truncate core tables like organization, user, token
    cur.execute("TRUNCATE TABLE metric, behavior, model CASCADE;")
    cur.close()


@pytest.fixture(scope="session")
def test_project_id(docker_compose_test_env) -> str:
    """
    Create a test project for integration tests that need a project_id.

    Returns the project ID that can be used by endpoint and test run tests.
    """
    url = f"http://localhost:{BACKEND_PORT}/projects/"
    headers = {"Authorization": f"Bearer {QUICK_START_TOKEN}", "Content-Type": "application/json"}

    # Create the test project
    project_data = {
        "name": "Integration Test Project",
        "description": "Project created for SDK integration tests",
    }

    response = requests.post(url, json=project_data, headers=headers)
    response.raise_for_status()
    project = response.json()

    print(f"{GREEN}✅ Created test project: {project['id']}{NC}")
    return project["id"]


@pytest.fixture(scope="function")
def db_cleanup(docker_compose_test_env):
    """
    Automatic database cleanup for integration tests.
    Runs automatically before and after EACH test.

    Truncates test-specific tables (metric, behavior, model) while
    preserving Quick Start data (organization, user, token).
    """
    # 🧼 Cleanup at START (before test runs)
    conn = None
    try:
        conn = _get_db_connection()
        _truncate_test_tables(conn)
        conn.close()
    except Exception as e:
        if conn:
            conn.close()
        print(f"⚠️  Warning: Could not clean database at start: {e}")

    yield  # Test runs here

    # 🧹 Cleanup at END (after test completes)
    print("🔄 Cleaning database after test...")
    conn = None
    try:
        conn = _get_db_connection()
        _truncate_test_tables(conn)
        conn.close()
    except Exception as e:
        if conn:
            conn.close()
        print(f"⚠️  Warning: Could not clean database at end: {e}")

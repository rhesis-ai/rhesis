import hashlib
import os
import subprocess
import time
from pathlib import Path
from typing import Generator

import psycopg2
import pytest
import requests
from psycopg2.extras import RealDictCursor

# ANSI color codes
BLUE = "\033[0;34m"
GREEN = "\033[0;32m"
RED = "\033[0;31m"
CYAN = "\033[0;36m"
NC = "\033[0m"  # No Color

DATABASE_PORT = 10000
BACKEND_PORT = 10001


@pytest.fixture(scope="session", autouse=True)
def set_env():
    os.environ["RHESIS_BASE_URL"] = f"http://localhost:{BACKEND_PORT}"
    os.environ["RHESIS_API_KEY"] = "rh-test-token"
    print(f"{GREEN}✅ Environment variables set for docker-compose mode{NC}")


def clear_all_tables() -> None:
    """Clear all data from key tables."""
    print(f"{BLUE}🗑️  Clearing database...{NC}")

    conn = None
    try:
        conn = psycopg2.connect(
            host="localhost",
            database="rhesis-db",
            user="rhesis-user",
            password="your-secured-password",
            port=DATABASE_PORT,
        )
        conn.autocommit = True
        cur = conn.cursor()

        # Truncate in order that respects foreign key constraints
        # CASCADE handles foreign key constraints automatically
        cur.execute("""
            TRUNCATE TABLE token, "user", organization, metric
            RESTART IDENTITY CASCADE;
        """)

        cur.close()
        conn.close()
        print(f"{GREEN}✅ Database cleared{NC}. Cleared tables: token, user, organization, metric")

    except psycopg2.Error as e:
        if conn:
            conn.close()
        print(f"⚠️  Warning: Could not clear database: {e}")


def setup_test_data() -> None:
    """Set up test data in the database."""
    print(f"{BLUE}🧪 Setting up test data...{NC}")

    # Set token value
    TOKEN_VALUE = "rh-test-token"

    # Generate token hash
    print(f"{BLUE}Generating token hash...{NC}")
    try:
        TOKEN_HASH = hashlib.sha256(TOKEN_VALUE.encode()).hexdigest()
    except ImportError as e:
        pytest.fail(f"❌ Failed to generate token hash: {e}")

    print(f"{BLUE}Token: {TOKEN_VALUE}{NC}")
    print(f"{BLUE}Hash: {TOKEN_HASH}{NC}")

    # Database connection parameters
    conn = None

    try:
        # Connect to the database
        print(f"{BLUE}Creating organization, user, and token...{NC}")
        conn = psycopg2.connect(
            host="localhost",
            database="rhesis-db",
            user="rhesis-user",
            password="your-secured-password",
            port=DATABASE_PORT,
        )
        conn.autocommit = False
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Execute the SQL query to create organization, user, token, and project
        sql = """
        -- Create organization and user
        WITH new_org AS (
            INSERT INTO organization (name)
            VALUES ('test_organization')
            RETURNING id
        ),
        new_user AS (
            INSERT INTO "user" (email, organization_id)
            SELECT 'test@example.com', id FROM new_org
            RETURNING id, organization_id
        ),
        new_token AS (
            INSERT INTO token (
                token,
                token_hash,
                token_type,
                user_id
            )
            SELECT
                %(token_value)s,
                %(token_hash)s,
                'bearer',
                new_user.id
            FROM new_user
            RETURNING user_id
        )
        -- Create project with specific ID "1234"
        INSERT INTO project (id, name, description, organization_id, user_id, owner_id)
        SELECT
            '12340000-0000-4000-8000-000000001234'::uuid,
            'Test Project',
            'Test project for integration tests',
            new_user.organization_id,
            new_user.id,
            new_user.id
        FROM new_user
        ON CONFLICT (id) DO NOTHING;
        """

        cur.execute(sql, {"token_value": TOKEN_VALUE, "token_hash": TOKEN_HASH})
        conn.commit()

        # Close the connection
        cur.close()
        conn.close()

        # Display the token prominently
        print()
        print(f"{GREEN}════════════════════════════════════════════════{NC}")
        print(f"{GREEN}✅ Test API Key Generated{NC}")
        print(f"{GREEN}════════════════════════════════════════════════{NC}")
        print(f"{CYAN}{TOKEN_VALUE}{NC}")
        print(f"{GREEN}════════════════════════════════════════════════{NC}")
        print()
        print(f"{GREEN}✅ Test project created with ID: 12340000-0000-0000-0000-000000001234{NC}")
        print()

        print(f"{GREEN}✅ Test data setup completed{NC}")

    except psycopg2.Error as e:
        if conn is not None:
            conn.rollback()
            conn.close()
        pytest.fail(f"❌ Failed to setup test data: {e}")
    except Exception as e:
        if conn is not None:
            conn.rollback()
            conn.close()
        pytest.fail(f"❌ Unexpected error: {e}")


@pytest.fixture(scope="session", autouse=True)
def docker_compose_test_env() -> Generator[dict, None, None]:
    """
    Set up isolated docker-compose environment for integration tests.

    This fixture ensures tests run in a clean, reproducible environment.
    """
    print(f"{BLUE}🐳 Starting isolated docker-compose environment{NC}")
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

    # Clear all tables before setting up test data
    clear_all_tables()

    # Setup test data (organization, user, and token)
    setup_test_data()

    # Yield test environment info
    test_config = {
        "base_url": f"http://localhost:{BACKEND_PORT}",
        "api_key": "rh-test-token",
    }

    # Yield test environment info
    yield test_config


@pytest.fixture(scope="function")
def db_cleanup(docker_compose_test_env):
    """
    Automatic database cleanup for integration tests.
    Runs automatically before and after EACH test.
    """
    # 🧼 Cleanup at START (before test runs)
    conn = None
    try:
        conn = psycopg2.connect(
            host="localhost",
            database="rhesis-db",
            user="rhesis-user",
            password="your-secured-password",
            port=DATABASE_PORT,
        )
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute("TRUNCATE TABLE metric, behavior CASCADE;")
        cur.close()
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
        conn = psycopg2.connect(
            host="localhost",
            database="rhesis-db",
            user="rhesis-user",
            password="your-secured-password",
            port=DATABASE_PORT,
        )
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute("TRUNCATE TABLE metric, behavior CASCADE;")
        cur.close()
        conn.close()
    except Exception as e:
        if conn:
            conn.close()
        print(f"⚠️  Warning: Could not clean database at end: {e}")

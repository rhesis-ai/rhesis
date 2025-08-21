import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from typing import Tuple

# Load environment variables
load_dotenv()

# Set test mode environment variable BEFORE importing any backend modules
os.environ["SQLALCHEMY_DB_MODE"] = "test"

# Now import backend modules after setting test mode
from rhesis.backend.app.main import app
from rhesis.backend.app.database import Base, get_db
from rhesis.backend.app import models



# Simple fixtures for testing markers functionality

@pytest.fixture
def sample_prompt():
    """🧠 Sample AI prompt for testing"""
    return "Generate tests for a financial chatbot that helps with loans"

@pytest.fixture
def mock_test_data():
    """📝 Mock test data structure"""
    return {
        "test_cases": [
            {"input": "What's my balance?", "expected": "account_inquiry"},
            {"input": "How do I apply for a loan?", "expected": "loan_application"}
        ]
    }

@pytest.fixture
def rhesis_api_key():
    """🔑 API key from environment for testing"""
    api_key = os.getenv("RHESIS_API_KEY")
    print(f"🔍 DEBUG: RHESIS_API_KEY from environment: {repr(api_key)}")
    if not api_key:
        # Fallback to mock key if no real key is available
        fallback_key = "rh-test1234567890abcdef"
        print(f"🔍 DEBUG: Using fallback key: {repr(fallback_key)}")
        return fallback_key
    print(f"🔍 DEBUG: Using environment API key: {repr(api_key)}")
    return api_key

# Test database configuration - PostgreSQL only
SQLALCHEMY_DATABASE_TEST_URL = os.getenv("SQLALCHEMY_DATABASE_TEST_URL")
if not SQLALCHEMY_DATABASE_TEST_URL:
    raise ValueError("SQLALCHEMY_DATABASE_TEST_URL environment variable is required for testing")

# Create separate test engine for PostgreSQL
test_engine = create_engine(
    SQLALCHEMY_DATABASE_TEST_URL,
    pool_pre_ping=True,
    pool_recycle=300
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

def override_get_db():
    """Override the get_db dependency for testing."""
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Set up the test database before any tests run."""
    # Create all tables in the test database
    Base.metadata.create_all(bind=test_engine)
    yield
    # Clean up after all tests are done
    Base.metadata.drop_all(bind=test_engine)

@pytest.fixture
def test_db():
    """🗄️ Provide a database session for testing with automatic rollback."""
    connection = test_engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()

@pytest.fixture
def client():
    """🌐 FastAPI test client with test database."""
    # Override the database dependency
    app.dependency_overrides[get_db] = override_get_db
    
    with TestClient(app) as test_client:
        yield test_client
    
    # Clean up the override
    app.dependency_overrides.clear()

@pytest.fixture
def authenticated_client(client, rhesis_api_key):
    """🔑 FastAPI test client with authentication headers."""
    print(f"🔍 DEBUG: Setting Authorization header with API key: {repr(rhesis_api_key)}")
    client.headers.update({"Authorization": f"Bearer {rhesis_api_key}"})
    print(f"🔍 DEBUG: Client headers now include: {dict(client.headers)}")
    return client


# === 🔑 DYNAMIC AUTHENTICATION FIXTURES ===

def get_authenticated_user_info(db) -> tuple[str | None, str | None]:
    """
    Retrieve the authenticated user and organization IDs from the API key.
    
    Args:
        db: Database session
        
    Returns:
        Tuple of (organization_id, user_id) as strings, or (None, None) if not found
    """
    try:
        from rhesis.backend.app import crud
    except ImportError:
        return None, None
        
    api_key = os.getenv("RHESIS_API_KEY")
    if not api_key:
        return None, None
    
    try:
        # Get token from database using the API key value
        token = crud.get_token_by_value(db, api_key)
        if not token:
            return None, None
            
        # Get user from the token's user_id
        user = crud.get_user_by_id(db, token.user_id)
        if not user:
            return None, None
            
        return str(user.organization_id), str(user.id)
        
    except Exception as e:
        print(f"⚠️ Warning: Could not retrieve authenticated user info: {e}")
        return None, None


@pytest.fixture(scope="session")
def authenticated_user_info() -> tuple[str, str]:
    """
    🔑 Get the authenticated user and organization IDs from API key
    
    This fixture retrieves the actual user and organization IDs that correspond
    to the RHESIS_API_KEY environment variable. This ensures tests use the
    correct authenticated context.
        
    Returns:
        Tuple of (organization_id, user_id) as strings
        
    Raises:
        pytest.skip: If API key is invalid or user not found
    """
    # Create a temporary database session for this session-scoped fixture
    session = TestingSessionLocal()
    try:
        org_id, user_id = get_authenticated_user_info(session)
        
        if not org_id or not user_id:
            pytest.skip("Could not retrieve authenticated user info from RHESIS_API_KEY")
        
        return org_id, user_id
    finally:
        session.close()


@pytest.fixture(scope="session") 
def test_org_id(authenticated_user_info) -> str:
    """🏢 Get the test organization ID from authenticated API key"""
    org_id, _ = authenticated_user_info
    return org_id


@pytest.fixture(scope="session")
def authenticated_user_id(authenticated_user_info) -> str:
    """👤 Get the authenticated user ID from API key"""
    _, user_id = authenticated_user_info
    return user_id

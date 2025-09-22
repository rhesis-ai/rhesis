import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from typing import Tuple

# Load environment variables from test directory first, then backend
load_dotenv()  # Try current directory first
load_dotenv("tests/.env")  # Load from test directory where RHESIS_API_KEY should be
load_dotenv("apps/backend/.env")  # Then backend directory for other vars

# Set test mode environment variable BEFORE importing any backend modules
os.environ["SQLALCHEMY_DB_MODE"] = "test"

# Now import backend modules after setting test mode
from rhesis.backend.app.main import app
from rhesis.backend.app.database import Base, get_db, get_database_url
from rhesis.backend.app import models
from rhesis.backend.app.constants import EntityType



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
    masked_key = f"{api_key[:3]}...{api_key[-4:]}" if api_key else None
    print(f"🔍 DEBUG: RHESIS_API_KEY from environment: {masked_key}")
    if not api_key:
        # Fallback to mock key if no real key is available
        fallback_key = "rh-test1234567890abcdef"
        fallback_masked = f"{fallback_key[:3]}...{fallback_key[-4:]}"
        print(f"🔍 DEBUG: Using fallback key: {fallback_masked}")
        return fallback_key
    print(f"🔍 DEBUG: Using environment API key: {masked_key}")
    return api_key

# Test database configuration - use the same logic as main database file
# This ensures consistency between test and production database connections
SQLALCHEMY_DATABASE_TEST_URL = get_database_url()

# Create test engine with the same configuration as production
# but optimized for testing (smaller pool sizes)
test_engine = create_engine(
    SQLALCHEMY_DATABASE_TEST_URL,
    # Reduced pool settings for testing
    pool_size=5,                   # Smaller than production (10)
    max_overflow=10,               # Smaller than production (20)
    pool_pre_ping=True,            # Same as production
    pool_recycle=3600,             # Same as production (1 hour)
    pool_timeout=10,               # Same as production
    # Same connection args as production
    connect_args={
        "connect_timeout": 10,          # Same as production
        "application_name": "rhesis-backend-test",  # Distinguish test connections
        "keepalives_idle": "300",       # Same as production
        "keepalives_interval": "10",    # Same as production
        "keepalives_count": "3",        # Same as production
        "tcp_user_timeout": "30000",    # Same as production
    }
)
TestingSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=test_engine,
    expire_on_commit=False,  # Same as production
)

@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Set up the test database before any tests run."""
    # Create all tables in the test database
    Base.metadata.create_all(bind=test_engine)
    yield
    # Clean up after all tests are done
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture(autouse=True)
def clean_test_database():
    """Clean test database between tests for isolation while preserving session-scoped auth data."""
    # Clean up BEFORE each test to ensure isolation
    try:
        with test_engine.connect() as connection:
            # Get session-scoped authentication data to preserve it (outside transaction)
            auth_user_id = None
            auth_org_id = None
            auth_token_ids = []
            
            try:
                # Try to get the authenticated user info from environment
                import os
                api_key = os.getenv("RHESIS_API_KEY")
                if api_key:
                    # Get the user and org that should be preserved
                    result = connection.execute(text("""
                        SELECT u.id as user_id, u.organization_id, array_agg(DISTINCT t.id) as token_ids
                        FROM "user" u 
                        JOIN token t ON t.user_id = u.id 
                        WHERE t.token = :api_key
                        GROUP BY u.id, u.organization_id
                    """), {"api_key": api_key})
                    
                    row = result.fetchone()
                    if row:
                        auth_user_id = str(row.user_id)
                        auth_org_id = str(row.organization_id) if row.organization_id else None
                        auth_token_ids = [str(tid) for tid in (row.token_ids or []) if tid]
                        print(f"🔐 Preserving auth data: user={auth_user_id}, org={auth_org_id}, tokens={len(auth_token_ids)}")
                
                # If no API key or auth data found, try to preserve ANY existing auth tokens
                # This prevents complete data wipeout when running tests without RHESIS_API_KEY
                if not auth_user_id:
                    result = connection.execute(text("""
                        SELECT u.id as user_id, u.organization_id, array_agg(DISTINCT t.id) as token_ids
                        FROM "user" u 
                        JOIN token t ON t.user_id = u.id 
                        GROUP BY u.id, u.organization_id
                        LIMIT 1
                    """))
                    
                    row = result.fetchone()
                    if row:
                        auth_user_id = str(row.user_id)
                        auth_org_id = str(row.organization_id) if row.organization_id else None
                        auth_token_ids = [str(tid) for tid in (row.token_ids or []) if tid]
                        print(f"🔐 Preserving fallback auth data: user={auth_user_id}, org={auth_org_id}, tokens={len(auth_token_ids)}")
                        
            except Exception as e:
                # If we can't get auth data, continue with normal cleanup
                print(f"⚠️ Could not retrieve auth data for preservation: {e}")
                pass
            
            # List of tables to clean (in correct dependency order - most dependent first)
            # Clean ALL test data but preserve ONLY core authentication data (tokens, users, organization)
            tables_to_clean = [
                # Level 1: Association tables (no dependencies, just references)
                'test_test_set',  # test.id + test_set.id
                'prompt_test_set',  # prompt.id + test_set.id  
                'behavior_metric',  # behavior.id + metric.id
                'risk_use_case',  # risk.id + use_case.id
                'prompt_use_case',  # prompt.id + use_case.id
                'tagged_item',  # tag.id + entity polymorphic
                
                # Level 2: Highly dependent entities (reference many other tables)
                'comment',  # -> user, organization (polymorphic entity refs)
                'test_result',  # -> test_configuration, test_run, prompt, test, status, user, organization
                
                # Level 3: Execution/runtime entities
                'test_run',  # -> user, status, test_configuration, organization
                'test_configuration',  # -> endpoint, category, topic, prompt, use_case, test_set, user, status, organization
                
                # Level 4: Test entities
                'test_context',  # -> test, organization, user
                'test',  # -> prompt, type_lookup, user(3x), topic, behavior, category, status, organization
                
                # Level 5: Content entities  
                'prompt',  # -> demographic, category(2x), topic, behavior, prompt, prompt_template, source, user, status
                'test_set',  # -> status, type_lookup, user(3x), organization
                'prompt_template',  # -> user, organization
                'model',  # -> user(2x), organization
                'task',  # -> user(2x), status, type_lookup, organization
                'metric',  # -> user(2x), organization
                'endpoint',  # -> user, organization
                'project',  # -> user(2x), status, organization
                
                # Level 6: Reference/lookup entities (clean everything - no preservation)
                'response_pattern',  # -> organization
                'risk',  # -> organization, user
                'use_case',  # -> organization, user
                'source',  # -> organization
                'behavior',  # -> organization, user  
                'category',  # -> organization, user
                'topic',  # -> organization, user
                'demographic',  # -> dimension, organization, user
                'dimension',  # -> organization, user
                'tag',  # -> (referenced by tagged_item)
                'type_lookup',  # -> organization, user
                'status',  # -> organization, user
                
                # Level 7: User-related tables (clean everything except auth tokens)
                'subscription',  # -> user, organization (CLEAN ALL)
                
                # Level 8: Core authentication tables (preserve ONLY auth user/org/tokens)
                'token',  # -> user, organization (PRESERVE AUTH TOKENS ONLY)
                'organization',  # -> user(2x) [owner_id, user_id] (PRESERVE AUTH ORG ONLY)
                '"user"',  # -> organization [organization_id] (PRESERVE AUTH USER ONLY)
            ]
                
            # Only clean if we have authentication data to preserve, or if explicitly requested
            # This prevents accidental complete data wipeout
            if auth_user_id and auth_org_id and auth_token_ids:
                print(f"🧹 Starting selective cleanup while preserving auth data...")
                
                # Clean each table in its own transaction to prevent cascading failures
                for table_name in tables_to_clean:
                    try:
                        with connection.begin():
                            if table_name == '"user"' and auth_user_id:
                                # Preserve the authenticated user
                                result = connection.execute(text(f'DELETE FROM {table_name} WHERE id != :auth_user_id'), 
                                                 {"auth_user_id": auth_user_id})
                                if result.rowcount > 0:
                                    print(f"  🗑️ Cleaned {result.rowcount} users (preserved auth user)")
                            elif table_name == 'organization' and auth_org_id:
                                # Preserve the authenticated user's organization
                                result = connection.execute(text(f'DELETE FROM {table_name} WHERE id != :auth_org_id'), 
                                                 {"auth_org_id": auth_org_id})
                                if result.rowcount > 0:
                                    print(f"  🗑️ Cleaned {result.rowcount} organizations (preserved auth org)")
                            elif table_name == 'token' and auth_token_ids:
                                # Preserve the authentication tokens
                                placeholders = ','.join([f':token_{i}' for i in range(len(auth_token_ids))])
                                token_params = {f'token_{i}': token_id for i, token_id in enumerate(auth_token_ids)}
                                result = connection.execute(text(f'DELETE FROM {table_name} WHERE id NOT IN ({placeholders})'), 
                                                 token_params)
                                if result.rowcount > 0:
                                    print(f"  🗑️ Cleaned {result.rowcount} tokens (preserved {len(auth_token_ids)} auth tokens)")
                            elif table_name == 'subscription':
                                # Clean ALL subscriptions (no preservation)
                                result = connection.execute(text(f'DELETE FROM {table_name}'))
                                if result.rowcount > 0:
                                    print(f"  🗑️ Cleaned {result.rowcount} subscriptions")
                            else:
                                # For all other tables (reference/lookup tables), clean everything
                                result = connection.execute(text(f'DELETE FROM {table_name}'))
                                if result.rowcount > 0:
                                    print(f"  🗑️ Cleaned {result.rowcount} rows from {table_name}")
                                
                    except Exception as e:
                        # If cleanup fails for a table, continue with others
                        # This is expected for tables that don't exist or have complex constraints
                        pass
                        
                print(f"✅ Selective cleanup completed")
            else:
                print(f"⚠️ Skipping cleanup - no auth data found to preserve. This prevents accidental data loss.")
                print(f"   To force cleanup, set RHESIS_API_KEY or ensure auth tokens exist in database.")
                            
    except Exception as e:
        # If cleanup fails completely, continue - tests might still work
        print(f"Database cleanup failed: {e}")
        pass
    
    yield  # Test runs here

@pytest.fixture
def test_db(test_org_id, authenticated_user_id):
    """🗄️ Provide a database session for testing - allows service code to manage transactions."""
    from rhesis.backend.app.database import clear_tenant_context, _current_tenant_organization_id, _current_tenant_user_id
    from sqlalchemy import text
    from uuid import UUID
    
    # Create session but let service code manage transactions (like production)
    db = TestingSessionLocal()
    try:
        # Set session variables (without SET LOCAL since no transaction context yet)
        if test_org_id:
            try:
                UUID(test_org_id)  # Validate UUID format
                db.execute(
                    text('SET "app.current_organization" = :org_id'), 
                    {"org_id": test_org_id}
                )
            except (ValueError, TypeError) as e:
                raise ValueError(f"Invalid test_org_id: {test_org_id}")
        
        if authenticated_user_id:
            try:
                UUID(authenticated_user_id)  # Validate UUID format
                db.execute(
                    text('SET "app.current_user" = :user_id'), 
                    {"user_id": authenticated_user_id}
                )
            except (ValueError, TypeError) as e:
                raise ValueError(f"Invalid authenticated_user_id: {authenticated_user_id}")
        
        # Store in context vars for any legacy code that might need it
        _current_tenant_organization_id.set(test_org_id)
        if authenticated_user_id:
            _current_tenant_user_id.set(authenticated_user_id)
            
        yield db
        # Let service code handle commit/rollback as it does in production
        
    finally:
        # Ensure any open transaction is rolled back
        try:
            if db.in_transaction():
                db.rollback()
        except Exception:
            pass
        
        # Clear context vars and close session
        clear_tenant_context()
        db.close()

@pytest.fixture
def client(test_db):
    """🌐 FastAPI test client with test database."""
    # Create override function that uses the same session as test fixtures
    def override_get_db():
        """Override the get_db dependency to use the same session as fixtures."""
        yield test_db
    
    # Override the database dependency
    app.dependency_overrides[get_db] = override_get_db
    
    with TestClient(app) as test_client:
        yield test_client
    
    # Clean up the override
    app.dependency_overrides.clear()

@pytest.fixture
def authenticated_client(client, rhesis_api_key):
    """🔑 FastAPI test client with authentication headers."""
    masked_key = f"{rhesis_api_key[:3]}...{rhesis_api_key[-4:]}" if rhesis_api_key else None
    print(f"🔍 DEBUG: Setting Authorization header with API key: {masked_key}")
    client.headers.update({"Authorization": f"Bearer {rhesis_api_key}"})
    # Mask the authorization header in debug output
    headers_debug = dict(client.headers)
    if 'authorization' in headers_debug:
        headers_debug['authorization'] = '***'
    print(f"🔍 DEBUG: Client headers now include: {headers_debug}")
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


@pytest.fixture
def test_entity_type(test_db, test_org_id, authenticated_user_id):
    """Create a test EntityType TypeLookup for testing Status relationships."""
    # Create a TypeLookup for EntityType.TEST
    entity_type = models.TypeLookup(
        type_name="EntityType",
        type_value=EntityType.TEST.value,
        organization_id=test_org_id,
        user_id=authenticated_user_id
    )
    test_db.add(entity_type)
    test_db.commit()
    test_db.refresh(entity_type)
    return entity_type


@pytest.fixture(scope="session")
def authenticated_user_id(authenticated_user_info) -> str:
    """👤 Get the authenticated user ID from API key"""
    _, user_id = authenticated_user_info
    return user_id

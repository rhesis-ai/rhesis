"""
Test setup utilities for backend testing.

This module provides utilities for setting up test environment including:
- Database initialization
- Test user and organization creation
- Initial data seeding
- Tenant context setup
"""

import os
import uuid
from datetime import datetime, timezone
from typing import Optional, Tuple

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

# Import backend modules
from rhesis.backend.app import crud, models
from rhesis.backend.app.auth.token_utils import generate_api_token
from rhesis.backend.app.database import get_database_url
from rhesis.backend.app.schemas import OrganizationCreate, UserCreate
from rhesis.backend.app.schemas.token import TokenCreate
from rhesis.backend.app.services.organization import load_initial_data
from rhesis.backend.app.utils.encryption import hash_token


def get_test_database_session() -> Session:
    """
    Create a test database session.

    Returns:
        Session: SQLAlchemy session configured for testing
    """
    # Ensure we're in test mode
    os.environ["SQLALCHEMY_DB_MODE"] = "test"

    # Get database URL for test environment
    database_url = get_database_url()

    # Create engine and session
    engine = create_engine(database_url)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    return SessionLocal()


def create_test_organization(db: Session, name: str = "Test Organization") -> models.Organization:
    """
    Create a test organization.

    Args:
        db: Database session
        name: Organization name

    Returns:
        Organization: Created organization
    """
    org_data = OrganizationCreate(
        name=name,
        description="Organization created for testing purposes",
        is_active=True,
        is_onboarding_complete=False,  # Will be set to True after initial data load
    )

    organization = crud.create_organization(db, org_data)
    print(f"✅ Created test organization: {organization.name} (ID: {organization.id})")

    return organization


def create_test_user(
    db: Session, organization_id: uuid.UUID, email: str = "test@rhesis.ai", name: str = "Test User"
) -> models.User:
    """
    Create a test user.

    Args:
        db: Database session
        organization_id: Organization ID to associate user with
        email: User email
        name: User name

    Returns:
        User: Created user
    """
    user_data = UserCreate(
        email=email,
        name=name,
        given_name="Test",
        family_name="User",
        auth0_id=f"test-auth0-id-{uuid.uuid4()}",
        is_active=True,
        is_superuser=False,  # Regular user by default
        organization_id=organization_id,
        last_login_at=datetime.now(timezone.utc),
    )

    user = crud.create_user(db, user_data)
    print(f"✅ Created test user: {user.email} (ID: {user.id})")

    return user


def create_test_api_token(
    db: Session, user: models.User, name: str = "Test API Token"
) -> models.Token:
    """
    Create a test API token for the user.

    Args:
        db: Database session
        user: User to create token for
        name: Token name

    Returns:
        Token: Created token
    """
    token_value = generate_api_token()

    token_data = TokenCreate(
        name=name,
        token=token_value,
        token_hash=hash_token(token_value),
        token_type="bearer",
        token_obfuscated=token_value[:3] + "..." + token_value[-4:],
        expires_at=None,  # No expiration for test token
        user_id=user.id,
        organization_id=user.organization_id,
    )

    token = crud.create_token(db=db, token=token_data)
    masked_token = f"{token_value[:3]}...{token_value[-4:]}"
    print(f"✅ Created test API token: {token.name} (Token: {masked_token})")

    # Set the token value in environment for tests to use
    os.environ["RHESIS_API_KEY"] = token_value
    print(f"🔑 Set RHESIS_API_KEY environment variable: {masked_token}")

    return token


def setup_initial_data(db: Session, organization_id: str, user_id: str) -> None:
    """
    Set up initial data for testing using the existing load_initial_data service.

    Args:
        db: Database session
        organization_id: Organization ID
        user_id: User ID
    """
    try:
        print(f"🌱 Loading initial data for organization {organization_id}")
        load_initial_data(db, organization_id, user_id)
        print("✅ Initial data loaded successfully")
    except Exception as e:
        print(f"❌ Error loading initial data: {e}")
        raise


def create_test_organization_and_user(
    db: Session,
    org_name: str = "Test Organization",
    user_email: str = "test@rhesis.ai",
    user_name: str = "Test User",
) -> Tuple[models.Organization, models.User, models.Token]:
    """
    Create test organization, user, and API token with proper setup.

    Args:
        db: Database session
        org_name: Organization name
        user_email: User email
        user_name: User name

    Returns:
        Tuple[Organization, User, Token]: Created organization, user, and API token
    """
    try:
        # Create organization
        organization = create_test_organization(db, org_name)

        # Create user
        user = create_test_user(db, organization.id, user_email, user_name)

        # Create API token for the user
        api_token = create_test_api_token(db, user)

        # Load initial data (uses get_db() with direct tenant context passing)
        print(f"🔧 Loading initial data for organization {organization.id}")
        setup_initial_data(db, str(organization.id), str(user.id))

        return organization, user, api_token

    except Exception as e:
        print(f"❌ Error creating test organization and user: {e}")
        db.rollback()
        raise


def cleanup_test_data(db: Session, organization_id: Optional[str] = None) -> None:
    """
    Clean up test data from database.

    Args:
        db: Database session
        organization_id: Specific organization ID to clean up (optional)
    """
    try:
        if organization_id:
            # Clean up specific organization data
            print(f"🧹 Cleaning up data for organization {organization_id}")

            # Use the existing rollback_initial_data function if available
            try:
                from rhesis.backend.app.services.organization import rollback_initial_data

                rollback_initial_data(db, organization_id)
                print(f"✅ Cleaned up organization {organization_id} data")
            except ImportError:
                print("⚠️ rollback_initial_data not available, performing manual cleanup")
                # Manual cleanup - delete organization and all related data
                org = (
                    db.query(models.Organization)
                    .filter(models.Organization.id == organization_id)
                    .first()
                )
                if org:
                    db.delete(org)
                    db.commit()
                    print(f"✅ Deleted organization {organization_id}")
        else:
            # Clean up all test data (be careful with this)
            print("🧹 Cleaning up all test data")
            # This is a more aggressive cleanup - use with caution
            test_orgs = (
                db.query(models.Organization).filter(models.Organization.name.like("%Test%")).all()
            )

            for org in test_orgs:
                print(f"🗑️ Deleting test organization: {org.name} (ID: {org.id})")
                db.delete(org)

            db.commit()
            print("✅ Test data cleanup completed")

    except Exception as e:
        print(f"❌ Error during cleanup: {e}")
        db.rollback()
        raise


def verify_test_environment() -> bool:
    """
    Verify that the test environment is properly configured.

    Returns:
        bool: True if environment is properly configured
    """
    required_env_vars = ["SQLALCHEMY_DB_MODE", "SQLALCHEMY_DATABASE_TEST_URL"]

    missing_vars = []
    for var in required_env_vars:
        if not os.getenv(var):
            missing_vars.append(var)

    if missing_vars:
        print(f"❌ Missing required environment variables: {missing_vars}")
        return False

    # Verify database mode is set to test
    if os.getenv("SQLALCHEMY_DB_MODE") != "test":
        print(f"❌ SQLALCHEMY_DB_MODE is not set to 'test': {os.getenv('SQLALCHEMY_DB_MODE')}")
        return False

    print("✅ Test environment verification passed")
    return True


def setup_test_environment() -> Tuple[models.Organization, models.User, models.Token]:
    """
    Main function to set up the complete test environment.

    This function:
    1. Verifies environment configuration
    2. Creates database session
    3. Creates test organization, user, and API token
    4. Loads initial data
    5. Returns organization, user, and token for use in tests

    Returns:
        Tuple[Organization, User, Token]: Created organization, user, and API token
    """
    print("🚀 Setting up test environment...")

    # Verify environment
    if not verify_test_environment():
        raise RuntimeError("Test environment verification failed")

    # Create database session
    db = get_test_database_session()

    try:
        # Check if test organization already exists
        existing_org = (
            db.query(models.Organization)
            .filter(models.Organization.name == "Test Organization")
            .first()
        )

        if existing_org:
            print(
                f"ℹ️ Test organization already exists: {existing_org.name} (ID: {existing_org.id})"
            )

            # Find associated test user
            existing_user = (
                db.query(models.User)
                .filter(
                    models.User.organization_id == existing_org.id,
                    models.User.email == "test@rhesis.ai",
                )
                .first()
            )

            if existing_user:
                print(f"ℹ️ Test user already exists: {existing_user.email} (ID: {existing_user.id})")

                # Find or create API token for existing user
                existing_token = (
                    db.query(models.Token)
                    .filter(
                        models.Token.user_id == existing_user.id,
                        models.Token.name == "Test API Token",
                    )
                    .first()
                )

                if existing_token:
                    print(f"ℹ️ Test API token already exists: {existing_token.name}")
                    # Set the token in environment
                    os.environ["RHESIS_API_KEY"] = existing_token.token
                    print(f"🔑 Set RHESIS_API_KEY environment variable: {existing_token.token}")
                    return existing_org, existing_user, existing_token
                else:
                    # Create new API token for existing user
                    api_token = create_test_api_token(db, existing_user)
                    return existing_org, existing_user, api_token

        # Create new test organization, user, and API token
        organization, user, api_token = create_test_organization_and_user(db)

        print("✅ Test environment setup completed successfully")
        print(f"   Organization: {organization.name} (ID: {organization.id})")
        print(f"   User: {user.email} (ID: {user.id})")
        print(f"   API Token: {api_token.name} (ID: {api_token.id})")

        return organization, user, api_token

    except Exception as e:
        print(f"❌ Failed to set up test environment: {e}")
        raise
    finally:
        db.close()


def reset_test_environment() -> None:
    """
    Reset the test environment by cleaning up all test data.
    """
    print("🔄 Resetting test environment...")

    db = get_test_database_session()
    try:
        cleanup_test_data(db)
        print("✅ Test environment reset completed")
    finally:
        db.close()


if __name__ == "__main__":
    """
    Command-line interface for test setup utilities.
    
    Usage:
        python test_setup.py setup    # Set up test environment
        python test_setup.py reset    # Reset test environment
        python test_setup.py verify   # Verify test environment
    """
    import sys

    if len(sys.argv) < 2:
        print("Usage: python test_setup.py [setup|reset|verify]")
        sys.exit(1)

    command = sys.argv[1].lower()

    if command == "setup":
        try:
            org, user, token = setup_test_environment()
            print(
                f"✅ Setup completed - Organization: {org.id}, User: {user.id}, Token: {token.id}"
            )
        except Exception as e:
            print(f"❌ Setup failed: {e}")
            sys.exit(1)

    elif command == "reset":
        try:
            reset_test_environment()
            print("✅ Reset completed")
        except Exception as e:
            print(f"❌ Reset failed: {e}")
            sys.exit(1)

    elif command == "verify":
        if verify_test_environment():
            print("✅ Environment verification passed")
            sys.exit(0)
        else:
            print("❌ Environment verification failed")
            sys.exit(1)

    else:
        print(f"Unknown command: {command}")
        print("Usage: python test_setup.py [setup|reset|verify]")
        sys.exit(1)

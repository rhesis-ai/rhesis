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
from contextlib import contextmanager
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
    # Get the configured database URL for the test environment
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
    db: Session,
    organization_id: Optional[uuid.UUID] = None,
    email: str = "test@rhesis.ai",
    name: str = "Test User",
) -> models.User:
    """
    Create a test user.

    Args:
        db: Database session
        organization_id: Organization ID to associate with, or None for
            pre-onboarding users who have not joined an organization yet
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
        organization_id=organization_id,
        last_login_at=datetime.now(timezone.utc),
    )

    user = crud.create_user(db, user_data)
    print(f"✅ Created test user: {user.email} (ID: {user.id})")

    return user


def create_test_api_token(
    db: Session, user: models.User, name: str = "Test API Token", set_env_var: bool = False
) -> models.Token:
    """
    Create a test API token for the user.

    Args:
        db: Database session
        user: User to create token for
        name: Token name
        set_env_var: Whether to point the shared ``RHESIS_API_KEY`` env var at
            this token. Only the one-time session-auth setup
            (``create_session_authentication``) should do this — every other
            caller (e.g. ``owner_client``, which authenticates via the token
            object directly) must pass ``False``. The env var is shared,
            process-global state read by code that looks up "the" authenticated
            user by env var alone (bypassing any per-test fixture); clobbering
            it from a one-off token orphans that lookup for every later test
            once this token's row is cleaned up.

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

    if set_env_var:
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


def ensure_owner_membership(db: Session, organization_id: uuid.UUID, user_id: uuid.UUID) -> None:
    """Guarantee *user_id* holds the built-in Owner role in *organization_id*.

    With RBAC available by default, every authenticated request from a test
    user is authorized against its ``organization_member`` role. Test users are
    created via ``crud.create_user`` which fires the EE default-role hook
    *before* ``owner_id`` is set (the FK requires the user to exist first), so
    the hook always seeds them as **Member** — which lacks org-admin and
    project-create capabilities, causing wholesale 403s. This creates the row
    if the hook never ran, or upgrades a Member row to Owner.

    The caller controls the transaction — this only flushes, never commits.
    No-op in community builds (no EE package) or when RBAC is unavailable.
    Idempotent: a row already at Owner is left untouched.
    """
    try:
        from rhesis.backend.app.features import FeatureName, FeatureRegistry
        from rhesis.backend.app.scope import bypass_tenant_filter
        from rhesis.backend.ee.rbac.models import OrganizationMember, Role
    except ImportError:
        return  # community build — no organization_member table

    with bypass_tenant_filter():
        organization = db.query(models.Organization).filter_by(id=organization_id).first()
        if organization is None or not FeatureRegistry.is_available(FeatureName.RBAC, organization):
            return

        owner_role = (
            db.query(Role).filter_by(name="Owner", is_built_in=True, organization_id=None).first()
        )
        if owner_role is None:
            # Built-in roles are seeded by an Alembic migration; if Owner is
            # missing the RBAC migrations didn't run — surface it loudly rather
            # than silently leaving the user without permissions.
            print(
                "⚠️ built-in Owner role not found (organization_id=None); "
                "cannot grant Owner to test user — RBAC migrations may be missing"
            )
            return

        member = (
            db.query(OrganizationMember)
            .filter_by(organization_id=organization_id, user_id=user_id)
            .first()
        )
        if member is None:
            db.add(
                OrganizationMember(
                    organization_id=organization_id,
                    user_id=user_id,
                    role_id=owner_role.id,
                )
            )
            db.flush()
        elif member.role_id != owner_role.id:
            member.role_id = owner_role.id
            db.flush()
            # Defensive: a prior test may have left this row demoted (e.g. a
            # bug bypassing temporarily_set_org_role's own bust_user calls)
            # while a "denied" decision for the old role is still cached.
            # Busting here means the fix-up above is never served stale.
            from rhesis.backend.app.services.permission_cache import get_permission_cache

            get_permission_cache().bust_user(user_id, organization_id)


@contextmanager
def temporarily_set_org_role(db: Session, organization_id, user_id, role_name: str = "None"):
    """Temporarily set *user_id*'s org-member role to the built-in *role_name*.

    Under RBAC, authorization is decided by the caller's ``organization_member``
    role, not ``organization.owner_id``. Tests that assert an unprivileged
    caller is denied must therefore demote the caller's *role* (the shared
    session user is otherwise an Owner). Defaults to "None" (empty permission
    set) so every capability check is denied.

    Busts the permission cache on entry and exit so the change (and its
    reversal) takes effect immediately, and restores the prior role on exit.
    No-op in community builds (no EE package). ``organization_id``/``user_id``
    may be str or UUID.
    """
    try:
        from rhesis.backend.app.scope import bypass_tenant_filter
        from rhesis.backend.app.services.permission_cache import get_permission_cache
        from rhesis.backend.ee.rbac.models import OrganizationMember, Role
    except ImportError:
        yield
        return

    org_uuid = (
        organization_id
        if isinstance(organization_id, uuid.UUID)
        else uuid.UUID(str(organization_id))
    )
    user_uuid = user_id if isinstance(user_id, uuid.UUID) else uuid.UUID(str(user_id))

    with bypass_tenant_filter():
        target_role = (
            db.query(Role).filter_by(name=role_name, is_built_in=True, organization_id=None).first()
        )
        member = (
            db.query(OrganizationMember)
            .filter_by(organization_id=org_uuid, user_id=user_uuid)
            .first()
        )
    if target_role is None or member is None:
        # Nothing to demote (community build, or user has no membership row).
        yield
        return

    original_role_id = member.role_id
    member.role_id = target_role.id
    db.flush()
    get_permission_cache().bust_user(user_uuid, org_uuid)
    try:
        yield
    finally:
        member.role_id = original_role_id
        db.flush()
        get_permission_cache().bust_user(user_uuid, org_uuid)


def create_test_organization_and_user(
    db: Session,
    org_name: str = "Test Organization",
    user_email: str = "test@rhesis.ai",
    user_name: str = "Test User",
    set_env_var: bool = False,
) -> Tuple[models.Organization, models.User, models.Token]:
    """
    Create test organization, user, and API token with proper setup.

    Args:
        db: Database session
        org_name: Organization name
        user_email: User email
        user_name: User name
        set_env_var: Whether to point the shared ``RHESIS_API_KEY`` env var at
            the newly created token. Defaults to ``False`` — only the one-time
            session-auth setup (``create_session_authentication``) should pass
            ``True``. See ``create_test_api_token`` for why.

    Returns:
        Tuple[Organization, User, Token]: Created organization, user, and API token
    """
    try:
        # Create organization
        organization = create_test_organization(db, org_name)

        # Create user
        user = create_test_user(db, organization.id, user_email, user_name)

        # Make the test user the org owner — mirrors real onboarding where the
        # first user to create an org becomes its owner.  Tests that need to
        # exercise non-owner behaviour should temporarily set org.owner_id = None
        # (or a different user ID) and restore it after the assertion.
        organization.owner_id = user.id
        db.flush()
        print(f"👑 Set org owner to user {user.id}")

        # Create API token for the user
        api_token = create_test_api_token(db, user, set_env_var=set_env_var)

        # Load initial data (uses get_db() with direct tenant context passing)
        print(f"🔧 Loading initial data for organization {organization.id}")
        setup_initial_data(db, str(organization.id), str(user.id))

        # Grant the test user the Owner role LAST — after setup_initial_data.
        # create_test_user() fired the EE default-role hook before owner_id was
        # set (the FK requires the user to exist first), seeding them as Member;
        # and load_initial_data runs project-scoped commits/rollbacks that would
        # clobber an earlier, uncommitted role change. Doing it here, after all
        # that, ensures the Owner grant is the final write the caller commits.
        ensure_owner_membership(db, organization.id, user.id)

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
    required_env_vars = ["DB_HOST", "DB_NAME", "APP_DB_USER", "APP_DB_PASS"]

    missing_vars = []
    for var in required_env_vars:
        if not os.getenv(var):
            missing_vars.append(var)

    if missing_vars:
        print(f"❌ Missing required environment variables: {missing_vars}")
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
                    # Create new API token for existing user. This is the
                    # standalone `python test_setup.py setup` CLI entrypoint,
                    # not a pytest fixture — it's meant to point RHESIS_API_KEY
                    # at this environment for manual/dev use, matching the
                    # existing_token branch above.
                    api_token = create_test_api_token(db, existing_user, set_env_var=True)
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

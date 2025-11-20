"""
Local Initialization

⚠️ WARNING: This module is for LOCAL USE ONLY!
It creates a default organization and admin user with known credentials.
DO NOT use this in production environments.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from rhesis.backend.app import crud, models
from rhesis.backend.app.services.organization import load_initial_data
from rhesis.backend.app.utils.encryption import hash_token
from rhesis.backend.app.utils.quick_start import is_quick_start_enabled
from rhesis.backend.logging import logger


def initialize_local_environment(db: Session) -> None:
    """
    Initialize local environment with default organization and user.

    Only runs when Quick Start mode is enabled (QUICK_START=true with validation).
    Creates:
    - Default organization "Local Org"
    - Default admin user admin@local.dev
    - Default API token rh-local-token

    This function is idempotent - it will not recreate resources if they already exist.
    """
    # Check if Quick Start mode is enabled
    if not is_quick_start_enabled():
        return

    logger.warning("=" * 80)
    logger.warning("⚠️  QUICK START MODE ENABLED")
    logger.warning("⚠️  Initializing default organization and user...")
    logger.warning("=" * 80)

    try:
        # Check if local organization already exists
        org = db.query(models.Organization).filter(models.Organization.name == "Local Org").first()

        if org:
            logger.info("ℹ️  Local organization already exists, skipping initialization.")

            # Check if user exists
            user = crud.get_user_by_email(db, "admin@local.dev")
            if user:
                logger.info("ℹ️  Local user already exists.")

                # Check if token exists
                # (check by user_id since we can't filter encrypted fields directly)
                token = (
                    db.query(models.Token)
                    .filter(models.Token.user_id == user.id)
                    .filter(models.Token.name == "Local Token")
                    .first()
                )

                if token:
                    logger.info("ℹ️  Local API token already exists.")
                else:
                    logger.info("ℹ️  Creating local API token...")
                    _create_local_token(db, user.id, org.id)
                    db.commit()

                # Check if initial data has been loaded (check for example project)
                example_project = (
                    db.query(models.Project)
                    .filter(models.Project.organization_id == org.id)
                    .filter(models.Project.name == "Example Project (Insurance Chatbot)")
                    .first()
                )

                if not example_project:
                    logger.info("📦 Loading initial seed data...")
                    load_initial_data(db, str(org.id), str(user.id))
                    db.commit()
                    logger.info("✅ Initial seed data loaded successfully!")
                else:
                    logger.info("ℹ️  Initial seed data already loaded.")

                _show_local_info()
                return

        # Create IDs
        org_id = uuid.uuid4()
        user_id = uuid.uuid4()
        current_time = datetime.now(timezone.utc)

        # Create admin user FIRST (without organization)
        logger.info("👤 Creating local admin user...")
        user = models.User(
            id=user_id,
            email="admin@local.dev",
            name="Local Admin",
            given_name="Local",
            family_name="Admin",
            is_active=True,
            is_superuser=True,
            organization_id=None,  # Set after organization is created
            auth0_id=None,  # No Auth0 ID for local
            last_login_at=current_time,
            created_at=current_time,
            updated_at=current_time,
            user_settings={"version": 1, "models": {"generation": {}, "evaluation": {}}},
        )
        db.add(user)
        db.flush()

        # Create organization (now user exists so foreign keys work)
        logger.info("📦 Creating local organization...")
        org = models.Organization(
            id=org_id,
            name="Local Org",
            display_name="Local Organization",
            description=(
                "Default organization for local deployment and testing. "
                "Created automatically for simplified local setup."
            ),
            is_active=True,
            is_onboarding_complete=True,
            owner_id=user_id,
            user_id=user_id,
            created_at=current_time,
            updated_at=current_time,
        )
        db.add(org)
        db.flush()

        # Update user with organization_id
        user.organization_id = org_id
        db.flush()

        # Create API token
        logger.info("🔑 Creating local API token...")
        _create_local_token(db, user_id, org_id)

        # Load initial seed data (example project, tests, etc.)
        logger.info("📦 Loading initial seed data...")
        load_initial_data(db, str(org_id), str(user_id))

        db.commit()

        logger.info("=" * 80)
        logger.info("✅ Local environment initialized successfully!")
        _show_local_info()
        logger.info("=" * 80)

    except Exception as e:
        logger.error(f"❌ Failed to initialize local environment: {str(e)}")
        logger.error("   This is not critical - you can still use the application.")
        db.rollback()


def _create_local_token(db: Session, user_id: uuid.UUID, organization_id: uuid.UUID) -> None:
    """Create the local API token."""
    token_id = uuid.uuid4()
    current_time = datetime.now(timezone.utc)
    token_value = "rh-local-token"

    token = models.Token(
        id=token_id,
        user_id=user_id,
        organization_id=organization_id,
        name="Local Token",
        token=token_value,
        token_hash=hash_token(token_value),
        token_type="bearer",
        token_obfuscated=token_value[:3] + "..." + token_value[-4:],
        expires_at=None,  # Never expires for local
        last_used_at=None,
        created_at=current_time,
        updated_at=current_time,
    )
    db.add(token)
    db.flush()


def _show_local_info() -> None:
    """Display local credentials and information."""
    logger.info("")
    logger.info("📋 LOCAL CREDENTIALS:")
    logger.info("   Organization: Local Org")
    logger.info("   User Email:   admin@local.dev")
    logger.info("   Login:        Auto-login enabled (navigate to http://localhost:3000)")
    logger.info("   API Token:    rh-local-token")
    logger.info("")
    logger.info("⚠️  WARNING: This is a local setup only!")
    logger.info("   Do not use these credentials in production.")
    logger.info("")

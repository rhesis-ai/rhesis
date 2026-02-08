"""Migrate all users to provider_type and external_provider_id

This migration ensures every user has a provider_type set:

1. Users with auth0_id: mapped based on the Auth0 ID prefix
   - google-oauth2|123 -> provider_type='google'
   - github|123 -> provider_type='github'
   - auth0|abc -> provider_type='email'
   - windowslive|123 / waad|123 -> provider_type='microsoft'
   - other formats -> provider_type='unknown'

2. Users without auth0_id: defaulted to provider_type='email'
   These are manually created or imported users with no prior
   auth provider association.

Revision ID: b2c3d4e5f6a8
Revises: a1c2d3e4f5g6
Create Date: 2026-01-22

"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a8"
down_revision: Union[str, None] = "a1c2d3e4f5g6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Migrate all users to have provider_type set.

    This migration:
    1. Maps auth0_id prefixes to provider_type values
    2. Extracts the external ID portion after the '|' separator
    3. Defaults users without auth0_id to provider_type='email'
    4. Only updates rows where provider_type is NULL (idempotent)
    """
    connection = op.get_bind()

    # Step 1: Map auth0_id to provider_type and external_provider_id
    connection.execute(
        text(
            """
            UPDATE "user" SET
                provider_type = CASE
                    WHEN auth0_id LIKE 'google-oauth2|%%' THEN 'google'
                    WHEN auth0_id LIKE 'github|%%' THEN 'github'
                    WHEN auth0_id LIKE 'auth0|%%' THEN 'email'
                    WHEN auth0_id LIKE 'windowslive|%%' THEN 'microsoft'
                    WHEN auth0_id LIKE 'waad|%%' THEN 'microsoft'
                    ELSE 'unknown'
                END,
                external_provider_id = CASE
                    WHEN auth0_id LIKE '%%|%%'
                        THEN split_part(auth0_id, '|', 2)
                    ELSE auth0_id
                END
            WHERE auth0_id IS NOT NULL
              AND provider_type IS NULL
        """
        )
    )

    # Step 2: Default users without auth0_id to 'email' provider
    connection.execute(
        text(
            """
            UPDATE "user" SET
                provider_type = 'email'
            WHERE auth0_id IS NULL
              AND provider_type IS NULL
        """
        )
    )

    # Step 3: Set is_email_verified=true for users migrated from Auth0 providers
    # (Google, GitHub, Auth0 email, etc. have all verified the email)
    connection.execute(
        text(
            """
            UPDATE "user" SET
                is_email_verified = true
            WHERE auth0_id IS NOT NULL
        """
        )
    )

    # Log migration results
    result = connection.execute(
        text(
            """
            SELECT
                provider_type,
                COUNT(*) as count,
                SUM(CASE
                    WHEN auth0_id IS NOT NULL THEN 1 ELSE 0
                END) as from_auth0,
                SUM(CASE
                    WHEN auth0_id IS NULL THEN 1 ELSE 0
                END) as no_auth0
            FROM "user"
            WHERE provider_type IS NOT NULL
            GROUP BY provider_type
            ORDER BY count DESC
        """
        )
    )

    print("\n=== User Provider Migration Results ===")
    print(f"  {'provider':<12} {'total':>6} {'auth0':>6} {'local':>6}")
    print(f"  {'-' * 36}")
    for row in result:
        print(f"  {row[0]:<12} {row[1]:>6} {row[2]:>6} {row[3]:>6}")
    print("========================================\n")


def downgrade() -> None:
    """
    Clear provider_type and external_provider_id for all migrated users.

    Note: This does not restore the original auth0_id values since
    the auth0_id column is preserved during the migration.
    """
    connection = op.get_bind()

    # Clear provider fields for users that were migrated from auth0
    connection.execute(
        text(
            """
            UPDATE "user" SET
                provider_type = NULL,
                external_provider_id = NULL
            WHERE auth0_id IS NOT NULL
              AND provider_type IS NOT NULL
        """
        )
    )

    # Clear provider fields for users that were defaulted to 'email'
    connection.execute(
        text(
            """
            UPDATE "user" SET
                provider_type = NULL
            WHERE auth0_id IS NULL
              AND provider_type = 'email'
        """
        )
    )

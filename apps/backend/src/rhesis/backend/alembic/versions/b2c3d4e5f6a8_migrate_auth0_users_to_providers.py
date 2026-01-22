"""Migrate auth0_id data to provider_type and external_provider_id

This migration maps existing auth0_id values to the new provider-agnostic
columns (provider_type and external_provider_id).

Auth0 ID formats:
- google-oauth2|123456789 -> provider_type='google', external_provider_id='123456789'
- github|12345678 -> provider_type='github', external_provider_id='12345678'
- auth0|abc123def456 -> provider_type='email', external_provider_id='abc123def456'

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
    Migrate auth0_id data to provider_type and external_provider_id columns.

    This migration:
    1. Maps auth0_id prefixes to provider_type values
    2. Extracts the external ID portion after the '|' separator
    3. Only updates rows where provider_type is NULL (not already migrated)
    """
    connection = op.get_bind()

    # Map auth0_id prefixes to provider_type and extract external_provider_id
    connection.execute(
        text(
            """
            UPDATE "user" SET
                provider_type = CASE
                    WHEN auth0_id LIKE 'google-oauth2|%' THEN 'google'
                    WHEN auth0_id LIKE 'github|%' THEN 'github'
                    WHEN auth0_id LIKE 'auth0|%' THEN 'email'
                    WHEN auth0_id LIKE 'windowslive|%' THEN 'microsoft'
                    WHEN auth0_id LIKE 'waad|%' THEN 'microsoft'
                    WHEN auth0_id IS NOT NULL THEN 'unknown'
                    ELSE NULL
                END,
                external_provider_id = CASE
                    WHEN auth0_id LIKE '%|%' THEN split_part(auth0_id, '|', 2)
                    ELSE auth0_id
                END
            WHERE auth0_id IS NOT NULL
              AND provider_type IS NULL
        """
        )
    )

    # Log migration results
    result = connection.execute(
        text(
            """
            SELECT provider_type, COUNT(*) as count
            FROM "user"
            WHERE provider_type IS NOT NULL
            GROUP BY provider_type
            ORDER BY count DESC
        """
        )
    )

    print("\n=== Auth0 User Migration Results ===")
    for row in result:
        print(f"  {row[0]}: {row[1]} users")
    print("=====================================\n")


def downgrade() -> None:
    """
    Clear provider_type and external_provider_id for migrated users.

    Note: This does not restore the original auth0_id values since
    the auth0_id column is preserved during the migration.
    """
    connection = op.get_bind()

    # Clear provider fields for users that were migrated from auth0
    # (identified by having both auth0_id and provider_type set)
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

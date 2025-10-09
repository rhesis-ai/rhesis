from alembic import op
import sqlalchemy as sa
from typing import Union, Sequence


# revision identifiers, used by Alembic.
revision: str = '0bcf30c3d836'
down_revision: Union[str, None] = 'bcf762626378'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Create a PostgreSQL procedure to delete a user and their related data without deleting the organization.
    
    This procedure removes:
    - The user record itself
    - User's tokens
    - User's personal test runs
    
    But PRESERVES:
    - The organization structure
    - Organization-wide resources (projects, tests, etc.)
    - Resources created by the user (become "ghost" records)
    
    This is useful when you need to remove a specific user but keep the organization intact.
    """
    
    op.execute("""
        CREATE OR REPLACE PROCEDURE delete_user_and_related_data(target_email text)
        LANGUAGE 'plpgsql'
        AS $$
        DECLARE
            target_user_id UUID;
        BEGIN
            -- Step 1: Get the user ID
            SELECT id INTO target_user_id FROM "user" WHERE email = target_email;

            IF target_user_id IS NULL THEN
                RAISE NOTICE 'User not found, exiting.';
                RETURN;
            END IF;

            -- Step 2: Delete user-specific data
            
            -- Delete user's tokens
            DELETE FROM token WHERE user_id = target_user_id;
            
            -- Delete test runs owned by this user
            DELETE FROM test_run WHERE user_id = target_user_id;
            
            -- Remove user from organization (if they belong to one)
            UPDATE "user"
            SET organization_id = NULL
            WHERE id = target_user_id;

            -- Step 3: Delete the user itself
            -- Note: Resources created by the user (tests, prompts, projects, etc.) 
            -- will remain as "ghost" records with the user_id reference
            DELETE FROM "user" WHERE id = target_user_id;
            
            RAISE NOTICE 'User % and their personal data have been deleted', target_email;
        END;
        $$;
        
        -- Add comment to document the procedure
        COMMENT ON PROCEDURE delete_user_and_related_data(text) IS 
        'Deletes a user and their personal data (tokens, test runs) but preserves the organization and organization-wide resources. Resources created by the user become "ghost" records. Use this when removing a specific user while keeping the organization intact.';
    """)


def downgrade() -> None:
    """Drop the user deletion procedure."""
    op.execute("DROP PROCEDURE IF EXISTS delete_user_and_related_data(text);")
from alembic import op
import sqlalchemy as sa
from typing import Union, Sequence



# revision identifiers, used by Alembic.
revision: str = 'bcf762626378'
down_revision: Union[str, None] = '4e087893c30f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Create a PostgreSQL procedure to completely delete a user and all their organization data.
    
    This is a HARD DELETE procedure that removes:
    - All organizations owned by the user
    - All users in those organizations
    - All organization-related data (tests, projects, endpoints, etc.)
    - The target user itself
    
    WARNING: This is irreversible and should only be used for complete data removal,
    such as for testing, data cleanup, or extreme cases.
    """
    
    op.execute("""
        CREATE OR REPLACE PROCEDURE delete_user_and_organization_data(target_email text)
        LANGUAGE 'plpgsql'
        AS $$
        DECLARE
            target_user_id UUID;
            org_ids UUID[];
        BEGIN
            -- Step 1: Get the user ID
            SELECT id INTO target_user_id FROM "user" WHERE email = target_email;

            IF target_user_id IS NULL THEN
                RAISE NOTICE 'User not found, exiting.';
                RETURN;
            END IF;

            -- Step 2: Collect organization IDs
            SELECT ARRAY_AGG(id) INTO org_ids 
            FROM organization 
            WHERE user_id = target_user_id OR owner_id = target_user_id;

            -- Step 3: Delete all org-related data
            IF org_ids IS NOT NULL AND array_length(org_ids, 1) IS NOT NULL THEN

                -- Delete other users in those organizations
                DELETE FROM "user"
                WHERE organization_id = ANY(org_ids)
                  AND id <> target_user_id;

                -- Detach the target user from any org
                UPDATE "user"
                SET organization_id = NULL
                WHERE id = target_user_id;

                -- Delete dependent entities
                DELETE FROM test_result 
                WHERE test_configuration_id IN (
                    SELECT id FROM test_configuration 
                    WHERE organization_id = ANY(org_ids)
                );

                DELETE FROM test_run 
                WHERE test_configuration_id IN (
                    SELECT id FROM test_configuration 
                    WHERE organization_id = ANY(org_ids)
                );

                DELETE FROM test_configuration WHERE organization_id = ANY(org_ids);
                DELETE FROM test_test_set WHERE test_set_id IN (SELECT id FROM test_set WHERE organization_id = ANY(org_ids));
                DELETE FROM test_context WHERE test_id IN (SELECT id FROM test WHERE organization_id = ANY(org_ids));
                DELETE FROM test WHERE organization_id = ANY(org_ids);
                DELETE FROM test_set WHERE organization_id = ANY(org_ids);
                DELETE FROM endpoint WHERE project_id IN (SELECT id FROM project WHERE organization_id = ANY(org_ids));
                DELETE FROM endpoint WHERE organization_id = ANY(org_ids);
                DELETE FROM project WHERE organization_id = ANY(org_ids);
                DELETE FROM response_pattern WHERE organization_id = ANY(org_ids);
                DELETE FROM prompt_use_case WHERE organization_id = ANY(org_ids);
                DELETE FROM prompt WHERE organization_id = ANY(org_ids);
                DELETE FROM prompt_template WHERE organization_id = ANY(org_ids);
                DELETE FROM risk_use_case WHERE organization_id = ANY(org_ids);
                DELETE FROM risk WHERE organization_id = ANY(org_ids);
                DELETE FROM use_case WHERE organization_id = ANY(org_ids);
                DELETE FROM behavior_metric WHERE organization_id = ANY(org_ids);
                DELETE FROM behavior WHERE organization_id = ANY(org_ids);
                DELETE FROM category WHERE organization_id = ANY(org_ids);
                DELETE FROM demographic WHERE organization_id = ANY(org_ids);
                DELETE FROM dimension WHERE organization_id = ANY(org_ids);
                DELETE FROM topic WHERE organization_id = ANY(org_ids);
                DELETE FROM subscription WHERE organization_id = ANY(org_ids);
                DELETE FROM metric WHERE organization_id = ANY(org_ids);
                DELETE FROM status WHERE organization_id = ANY(org_ids);
                DELETE FROM token WHERE organization_id = ANY(org_ids);
                DELETE FROM type_lookup WHERE organization_id = ANY(org_ids);
                DELETE FROM tagged_item WHERE organization_id = ANY(org_ids);
                DELETE FROM tag WHERE organization_id = ANY(org_ids);

                UPDATE organization
                SET is_onboarding_complete = false,
                    user_id = NULL,
                    owner_id = NULL
                WHERE id = ANY(org_ids);

                -- Finally, delete the organizations
                DELETE FROM organization WHERE id = ANY(org_ids);
            END IF;

            -- Step 4: Clean up test runs owned by this user
            DELETE FROM test_run WHERE user_id = target_user_id;

            -- Step 5: Delete the user itself
            DELETE FROM "user" WHERE id = target_user_id;
            
            RAISE NOTICE 'User % and all related data have been deleted', target_email;
        END;
        $$;
        
        -- Add comment to document the procedure
        COMMENT ON PROCEDURE delete_user_and_organization_data(text) IS 
        'HARD DELETE: Completely removes a user and all their organization data. This is irreversible and should only be used for complete data removal (testing, cleanup, or extreme cases). Use gdpr_anonymize_user() for GDPR compliance instead.';
    """)


def downgrade() -> None:
    """Drop the hard delete procedure."""
    op.execute("DROP PROCEDURE IF EXISTS delete_user_and_organization_data(text);")
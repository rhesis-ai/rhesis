from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a939dc9b4168"
down_revision: Union[str, None] = "792098eebe5f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Step 1: Add EntityType "Task" to type_lookup table
    op.execute("""
        WITH new_entries AS (
            SELECT *
            FROM (
                VALUES
                    ('EntityType', 'Task', 'Entity type for tasks')
            ) AS vals(type_name, type_value, description)
        ),
        orgs AS (
            SELECT DISTINCT organization_id FROM type_lookup
        )
        INSERT INTO type_lookup (type_name, type_value, description, organization_id)
        SELECT 
            n.type_name,
            n.type_value,
            n.description,
            o.organization_id
        FROM new_entries n
        CROSS JOIN orgs o
        WHERE NOT EXISTS (
            SELECT 1 FROM type_lookup existing
            WHERE existing.type_name = n.type_name
              AND existing.type_value = n.type_value
              AND existing.organization_id = o.organization_id
        );
    """)

    # Step 2: Add TaskPriority entries to type_lookup table
    op.execute("""
        WITH new_entries AS (
            SELECT *
            FROM (
                VALUES
                    ('TaskPriority', 'Low', 'Low priority task'),
                    ('TaskPriority', 'Medium', 'Medium priority task'),
                    ('TaskPriority', 'High', 'High priority task')
            ) AS vals(type_name, type_value, description)
        ),
        orgs AS (
            SELECT DISTINCT organization_id FROM type_lookup
        )
        INSERT INTO type_lookup (type_name, type_value, description, organization_id)
        SELECT 
            n.type_name,
            n.type_value,
            n.description,
            o.organization_id
        FROM new_entries n
        CROSS JOIN orgs o
        WHERE NOT EXISTS (
            SELECT 1 FROM type_lookup existing
            WHERE existing.type_name = n.type_name
              AND existing.type_value = n.type_value
              AND existing.organization_id = o.organization_id
        );
    """)

    # Step 3: Add Task status entries to status table
    op.execute("""
        WITH orgs AS (
            SELECT id AS organization_id
            FROM public.organization
        ),
        entity_types AS (
            SELECT tl.organization_id, tl.id AS entity_type_id
            FROM public.type_lookup tl
            WHERE tl.type_name = 'EntityType' AND tl.type_value = 'Task'
        ),
        org_entity_mapping AS (
            SELECT o.organization_id, et.entity_type_id
            FROM orgs o
            JOIN entity_types et ON o.organization_id = et.organization_id
        ),
        to_insert AS (
            SELECT 
                status_info.name,
                status_info.description,
                oem.entity_type_id,
                oem.organization_id,
                substring(md5(random()::text), 1, 10) AS nano_id
            FROM 
                org_entity_mapping oem,
                (VALUES
                    ('Open', 'Newly created, not yet started'),
                    ('In Progress', 'Currently being worked on'),
                    ('Completed', 'Work finished successfully'),
                    ('Cancelled', 'Task no longer needed')
                ) AS status_info(name, description)
        )
        INSERT INTO public.status (name, description, entity_type_id, organization_id, nano_id)
        SELECT 
            t.name,
            t.description,
            t.entity_type_id,
            t.organization_id,
            t.nano_id
        FROM to_insert t
        WHERE NOT EXISTS (
            SELECT 1
            FROM public.status s
            WHERE s.name = t.name
              AND s.organization_id = t.organization_id
              AND s.entity_type_id = t.entity_type_id
        );
    """)


def downgrade() -> None:
    # First, update any tasks that reference Task statuses to use a different status
    # We'll set them to use the first available status for the same organization
    op.execute("""
        UPDATE public.task 
        SET status_id = (
            SELECT s.id 
            FROM public.status s 
            WHERE s.organization_id = task.organization_id 
              AND s.name != 'Open' 
              AND s.name != 'In Progress' 
              AND s.name != 'Completed' 
              AND s.name != 'Cancelled'
            LIMIT 1
        )
        WHERE status_id IN (
            SELECT s.id 
            FROM public.status s
            JOIN public.type_lookup tl ON s.entity_type_id = tl.id
            WHERE s.name IN ('Open', 'In Progress', 'Completed', 'Cancelled')
              AND tl.type_name = 'EntityType' 
              AND tl.type_value = 'Task'
        );
    """)

    # Update any tasks that reference TaskPriority to set priority_id to NULL
    op.execute("""
        UPDATE public.task 
        SET priority_id = NULL
        WHERE priority_id IN (
            SELECT tl.id 
            FROM public.type_lookup tl 
            WHERE tl.type_name = 'TaskPriority' 
              AND tl.type_value IN ('Low', 'Medium', 'High')
        );
    """)

    # Remove Task status entries from status table
    op.execute("""
        DELETE FROM public.status 
        WHERE name IN ('Open', 'In Progress', 'Completed', 'Cancelled')
          AND entity_type_id IN (
              SELECT tl.id 
              FROM public.type_lookup tl 
              WHERE tl.type_name = 'EntityType' AND tl.type_value = 'Task'
          );
    """)

    # Remove TaskPriority entries from type_lookup table
    op.execute("""
        DELETE FROM type_lookup 
        WHERE type_name = 'TaskPriority' 
          AND type_value IN ('Low', 'Medium', 'High');
    """)

    # Remove EntityType "Task" entry from type_lookup table
    op.execute("""
        DELETE FROM type_lookup 
        WHERE type_name = 'EntityType' 
          AND type_value = 'Task';
    """)

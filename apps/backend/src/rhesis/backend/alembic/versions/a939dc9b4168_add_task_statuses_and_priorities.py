from typing import Sequence, Union

from alembic import op

# Import our simple template loader
from rhesis.backend.alembic.utils.template_loader import (
    load_cleanup_priority_references_template,
    load_cleanup_references_template,
    load_cleanup_status_template,
    load_cleanup_type_lookup_template,
    load_status_template,
    load_type_lookup_template,
)

# revision identifiers, used by Alembic.
revision: str = "a939dc9b4168"
down_revision: Union[str, None] = "792098eebe5f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Step 1: Add EntityType "Task" to type_lookup table
    entity_type_values = "('EntityType', 'Task', 'Entity type for tasks')"
    op.execute(load_type_lookup_template(entity_type_values))

    # Step 2: Add TaskPriority entries to type_lookup table
    priority_values = """
        ('TaskPriority', 'Low', 'Low priority task'),
        ('TaskPriority', 'Medium', 'Medium priority task'),
        ('TaskPriority', 'High', 'High priority task')
    """.strip()
    op.execute(load_type_lookup_template(priority_values))

    # Step 3: Add Task status entries to status table
    status_values = """
        ('Open', 'Newly created, not yet started'),
        ('In Progress', 'Currently being worked on'),
        ('Completed', 'Work finished successfully'),
        ('Cancelled', 'Task no longer needed')
    """.strip()
    op.execute(load_status_template("EntityType", "Task", status_values))


def downgrade() -> None:
    # Step 1: Update any tasks that reference Task statuses to use a different status
    status_values = "'Open', 'In Progress', 'Completed', 'Cancelled'"
    op.execute(
        load_cleanup_references_template("task", "status", "EntityType", "Task", status_values)
    )

    # Step 2: Update any tasks that reference TaskPriority to set priority_id to NULL
    priority_values = "'Low', 'Medium', 'High'"
    op.execute(
        load_cleanup_priority_references_template(
            "task", "priority", "TaskPriority", priority_values
        )
    )

    # Step 3: Remove Task status entries from status table
    status_names = "'Open', 'In Progress', 'Completed', 'Cancelled'"
    op.execute(load_cleanup_status_template("EntityType", "Task", status_names))

    # Step 4: Remove TaskPriority entries from type_lookup table
    op.execute(load_cleanup_type_lookup_template("TaskPriority", priority_values))

    # Step 5: Remove EntityType "Task" entry from type_lookup table
    entity_type_values = "'Task'"
    op.execute(load_cleanup_type_lookup_template("EntityType", entity_type_values))

"""
Simple template loader for Alembic migrations.

This utility loads SQL templates and replaces placeholders with provided values.
Much simpler than the previous sql_generator approach.
"""

from pathlib import Path
from typing import Dict


def load_template(template_name: str, replacements: Dict[str, str]) -> str:
    """
    Load a SQL template and replace placeholders with provided values.

    Args:
        template_name: Name of the template file (without .sql extension)
        replacements: Dictionary of placeholder -> replacement value mappings

    Returns:
        SQL string with placeholders replaced
    """
    # Get the templates directory
    current_dir = Path(__file__).parent
    templates_dir = current_dir.parent / "templates"
    template_path = templates_dir / f"{template_name}.sql"

    if not template_path.exists():
        raise FileNotFoundError(f"Template not found: {template_path}")

    # Read the template
    with open(template_path, "r") as f:
        template_content = f.read()

    # Replace placeholders
    for placeholder, value in replacements.items():
        template_content = template_content.replace(f"{{{{{placeholder}}}}}", value)

    return template_content


def load_type_lookup_template(values_clause: str) -> str:
    """
    Load type_lookup template with VALUES clause.

    Args:
        values_clause: SQL VALUES clause for the entries

    Returns:
        Complete SQL for inserting type_lookup entries
    """
    return load_template("type_lookup_template", {"VALUES_PLACEHOLDER": values_clause})


def load_status_template(type_name: str, entity_type: str, status_values_clause: str) -> str:
    """
    Load status template with type name, entity type and VALUES clause.

    Args:
        type_name: The type name in type_lookup (e.g., 'EntityType', 'CustomType')
        entity_type: The entity type (e.g., 'Task', 'Project')
        status_values_clause: SQL VALUES clause for the status entries

    Returns:
        Complete SQL for inserting status entries
    """
    return load_template(
        "status_template",
        {
            "TYPE_NAME": type_name,
            "ENTITY_TYPE": entity_type,
            "STATUS_VALUES_PLACEHOLDER": status_values_clause,
        },
    )


def load_cleanup_type_lookup_template(type_name: str, type_values_clause: str) -> str:
    """
    Load cleanup template for type_lookup entries.

    Args:
        type_name: The type name to clean up (e.g., 'TaskPriority', 'EntityType')
        type_values_clause: SQL VALUES clause for the type values to remove

    Returns:
        Complete SQL for cleaning up type_lookup entries
    """
    return load_template(
        "cleanup_type_lookup_template",
        {"TYPE_NAME": type_name, "TYPE_VALUES_PLACEHOLDER": type_values_clause},
    )


def load_cleanup_status_template(type_name: str, entity_type: str, status_names_clause: str) -> str:
    """
    Load cleanup template for status entries.

    Args:
        type_name: The type name in type_lookup (e.g., 'EntityType', 'CustomType')
        entity_type: The entity type to clean up (e.g., 'Task', 'Project')
        status_names_clause: SQL VALUES clause for the status names to remove

    Returns:
        Complete SQL for cleaning up status entries
    """
    return load_template(
        "cleanup_status_template",
        {
            "TYPE_NAME": type_name,
            "ENTITY_TYPE": entity_type,
            "STATUS_NAMES_PLACEHOLDER": status_names_clause,
        },
    )


def load_cleanup_references_template(
    table_name: str, reference_type: str, type_name: str, entity_type: str, values_clause: str
) -> str:
    """
    Load cleanup template for entity references.

    Args:
        table_name: The table name to update (e.g., 'task', 'project', 'model')
        reference_type: The reference type ('status' or 'priority')
        type_name: The type name in type_lookup (e.g., 'EntityType', 'CustomType')
        entity_type: The entity type (e.g., 'Task', 'Project')
        values_clause: SQL VALUES clause for the values to clean up

    Returns:
        Complete SQL for cleaning up entity references
    """
    return load_template(
        "cleanup_references_template",
        {
            "TABLE_NAME": table_name,
            "REFERENCE_TYPE": reference_type,
            "TYPE_NAME": type_name,
            "ENTITY_TYPE": entity_type,
            "VALUES_PLACEHOLDER": values_clause,
        },
    )


def load_cleanup_priority_references_template(
    table_name: str, priority_column: str, type_name: str, type_values_clause: str
) -> str:
    """
    Load cleanup template for entity priority references.

    Args:
        table_name: The table name to update (e.g., 'task', 'project', 'model')
        priority_column: The priority column name (e.g., 'priority', 'urgency')
        type_name: The type name in type_lookup (e.g., 'TaskPriority', 'CustomPriority')
        type_values_clause: SQL VALUES clause for the type values to clean up

    Returns:
        Complete SQL for cleaning up entity priority references
    """
    return load_template(
        "cleanup_priority_references_template",
        {
            "TABLE_NAME": table_name,
            "PRIORITY_COLUMN": priority_column,
            "TYPE_NAME": type_name,
            "TYPE_VALUES_PLACEHOLDER": type_values_clause,
        },
    )

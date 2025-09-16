# Alembic SQL Template System

This directory contains a simple, reusable template system for database migrations that eliminates code duplication and provides a consistent way to manage database data.

## Overview

Instead of hardcoding SQL statements in migration files, this system uses simple templates that can be parameterized with data directly from the migration file. This approach:

- **Eliminates code duplication** - No more copying SQL between migrations
- **Ensures consistency** - All data insertions follow the same pattern
- **Makes maintenance easier** - Changes to the pattern only need to be made in templates
- **Provides reusability** - Easy to add new data types using existing templates
- **Simple and lightweight** - No complex Python generators, just templates and data

## Directory Structure

```
alembic/
├── templates/                    # SQL templates
│   ├── type_lookup_template.sql  # Template for type_lookup entries
│   ├── status_template.sql       # Template for status entries
│   ├── cleanup_type_lookup_template.sql  # Template for cleaning up type_lookup entries
│   ├── cleanup_status_template.sql       # Template for cleaning up status entries
│   ├── cleanup_references_template.sql   # Template for cleaning up entity references
│   └── cleanup_priority_references_template.sql  # Template for cleaning up priority references
├── utils/                        # Python utilities
│   └── template_loader.py        # Simple template loader
└── versions/                     # Migration files
    └── a939dc9b4168_add_task_statuses_and_priorities.py
```

## Quick Start

### 1. Using Template Loader

The simplest approach - just load templates with your data:

```python
from rhesis.backend.alembic.utils.template_loader import load_type_lookup_template, load_status_template

def upgrade() -> None:
    # Add entity type
    entity_values = "('EntityType', 'Project', 'Entity type for projects')"
    op.execute(load_type_lookup_template(entity_values))
    
    # Add priority system
    priority_values = """
        ('ProjectPriority', 'High', 'High priority project'),
        ('ProjectPriority', 'Normal', 'Normal priority project'),
        ('ProjectPriority', 'Low', 'Low priority project')
    """.strip()
    op.execute(load_type_lookup_template(priority_values))
    
    # Add statuses
    status_values = """
        ('Planning', 'Project is in planning phase'),
        ('Active', 'Project is currently active'),
        ('Completed', 'Project has been completed')
    """.strip()
    op.execute(load_status_template('Project', status_values))
```

### 2. Direct Template Usage

You can also use templates directly by reading and replacing placeholders:

```python
from rhesis.backend.alembic.utils.template_loader import load_template

def upgrade() -> None:
    # Custom template usage
    sql = load_template("type_lookup_template", {
        "VALUES_PLACEHOLDER": "('CustomType', 'Value1', 'Description 1')"
    })
    op.execute(sql)
```

## Available Templates

### 1. Type Lookup Template (`type_lookup_template.sql`)

Used for inserting entries into the `type_lookup` table. Supports:
- Entity types (e.g., 'Task', 'Project', 'Bug')
- Priority systems (e.g., 'TaskPriority', 'BugPriority')
- Configuration values (e.g., 'SystemConfig')
- Any other categorized data

**Parameters:**
- `{{VALUES_PLACEHOLDER}}` - Replaced with VALUES clauses for the entries

### 2. Status Template (`status_template.sql`)

Used for inserting entries into the `status` table. Supports:
- Status entries for any entity type
- Automatic organization mapping
- Duplicate prevention

**Parameters:**
- `{{ENTITY_TYPE}}` - The entity type (e.g., 'Task', 'Project')
- `{{STATUS_VALUES_PLACEHOLDER}}` - Replaced with VALUES clauses for status entries

## API Reference

### SQLTemplateGenerator Class

#### Methods

- `generate_type_lookup_sql(entries: List[Dict[str, str]]) -> str`
  - Generate SQL for type_lookup entries
  - `entries`: List of dicts with 'type_name', 'type_value', 'description'

- `generate_status_sql(entity_type: str, status_entries: List[Dict[str, str]]) -> str`
  - Generate SQL for status entries
  - `entity_type`: The entity type name
  - `status_entries`: List of dicts with 'name', 'description'

- `generate_cleanup_type_lookup_sql(type_name: str, type_values: List[str]) -> str`
  - Generate cleanup SQL for type_lookup entries

- `generate_cleanup_status_sql(entity_type: str, status_names: List[str]) -> str`
  - Generate cleanup SQL for status entries

### Pre-built Functions

- `generate_task_entity_type_sql() -> str`
- `generate_task_priority_sql() -> str`
- `generate_task_status_sql() -> str`
- `generate_task_cleanup_sql() -> Dict[str, str]`

## Migration Best Practices

### 1. Upgrade Function

```python
def upgrade() -> None:
    # Use pre-built functions when available
    op.execute(generate_task_entity_type_sql())
    op.execute(generate_task_priority_sql())
    op.execute(generate_task_status_sql())
    
    # Or use generator for custom data
    generator = get_sql_generator()
    custom_sql = generator.generate_type_lookup_sql(custom_entries)
    op.execute(custom_sql)
```

### 2. Downgrade Function

```python
def downgrade() -> None:
    # Use pre-built cleanup functions
    cleanup_sql = generate_task_cleanup_sql()
    op.execute(cleanup_sql['task_status_cleanup'])
    op.execute(cleanup_sql['task_priority_cleanup'])
    # ... etc
    
    # Or use generator for custom cleanup
    generator = get_sql_generator()
    cleanup_sql = generator.generate_cleanup_type_lookup_sql('CustomType', ['Value1', 'Value2'])
    op.execute(cleanup_sql)
```

### 3. Order of Operations

**Upgrade:**
1. Add entity types first
2. Add priority/configuration types
3. Add statuses (depends on entity types)

**Downgrade:**
1. Update foreign key references first
2. Remove statuses
3. Remove priority/configuration types
4. Remove entity types last

## Examples

The README above contains comprehensive examples including:
- Adding new entity types
- Creating priority systems
- Adding status systems
- Custom data management
- Cleanup operations
- Complete migration examples

## Available Templates

### 1. Type Lookup Template (`type_lookup_template.sql`)

- **Purpose**: Inserts new entries into the `type_lookup` table.
- **Placeholders**:
  - `{{VALUES_PLACEHOLDER}}`: A comma-separated string of `(type_name, type_value, description)` tuples.
- **Example Usage**:
  ```python
  values = "('EntityType', 'NewEntity', 'Description of new entity')"
  op.execute(load_type_lookup_template(values))
  ```

### 2. Status Template (`status_template.sql`)

- **Purpose**: Inserts new entries into the `status` table, linked to a specific `entity_type`.
- **Placeholders**:
  - `{{TYPE_NAME}}`: The `type_name` in `type_lookup` that defines the entity type (e.g., 'EntityType').
  - `{{ENTITY_TYPE}}`: The `type_value` in `type_lookup` that identifies the entity (e.g., 'Task', 'Project').
  - `{{STATUS_VALUES_PLACEHOLDER}}`: A comma-separated string of `(name, description)` tuples for the statuses.
- **Example Usage**:
  ```python
  status_values = """
      ('New', 'Newly created status'),
      ('Approved', 'Approved status')
  """.strip()
  op.execute(load_status_template('EntityType', 'NewEntity', status_values))
  ```

### 3. Cleanup Type Lookup Template (`cleanup_type_lookup_template.sql`)

- **Purpose**: Deletes entries from the `type_lookup` table.
- **Placeholders**:
  - `{{TYPE_NAME}}`: The `type_name` to clean up.
  - `{{TYPE_VALUES_PLACEHOLDER}}`: A comma-separated string of `type_value`s to remove (e.g., `'Value1', 'Value2'`).
- **Example Usage**:
  ```python
  values = "'NewEntity', 'AnotherEntity'"
  op.execute(load_cleanup_type_lookup_template('EntityType', values))
  ```

### 4. Cleanup Status Template (`cleanup_status_template.sql`)

- **Purpose**: Deletes entries from the `status` table for a specific `entity_type`.
- **Placeholders**:
  - `{{TYPE_NAME}}`: The `type_name` in `type_lookup` that defines the entity type (e.g., 'EntityType').
  - `{{ENTITY_TYPE}}`: The `type_value` in `type_lookup` that identifies the entity.
  - `{{STATUS_NAMES_PLACEHOLDER}}`: A comma-separated string of `name`s of statuses to remove.
- **Example Usage**:
  ```python
  status_names = "'New', 'Approved'"
  op.execute(load_cleanup_status_template('EntityType', 'NewEntity', status_names))
  ```

### 5. Cleanup References Template (`cleanup_references_template.sql`)

- **Purpose**: Updates entity table references (e.g., `status_id`, `priority_id`) to `NULL` or another valid ID before the actual status/priority entries are deleted. This prevents foreign key violations.
- **Placeholders**:
  - `{{TABLE_NAME}}`: The table name to update (e.g., 'task', 'project', 'model').
  - `{{REFERENCE_TYPE}}`: The column name to update (e.g., 'status', 'priority').
  - `{{TYPE_NAME}}`: The `type_name` in `type_lookup` that defines the entity type (e.g., 'EntityType').
  - `{{ENTITY_TYPE}}`: The `type_value` in `type_lookup` that identifies the entity (e.g., 'Task').
  - `{{VALUES_PLACEHOLDER}}`: A comma-separated string of `name`s or `type_value`s that are being removed.
- **Example Usage**:
  ```python
  status_values = "'New', 'Approved'"
  op.execute(load_cleanup_references_template('task', 'status', 'EntityType', 'Task', status_values))
  ```

### 6. Cleanup Priority References Template (`cleanup_priority_references_template.sql`)

- **Purpose**: Updates entity table priority references to `NULL` before deleting priority entries. This prevents foreign key violations.
- **Placeholders**:
  - `{{TABLE_NAME}}`: The table name to update (e.g., 'task', 'project', 'model').
  - `{{PRIORITY_COLUMN}}`: The priority column name (e.g., 'priority', 'urgency').
  - `{{TYPE_NAME}}`: The `type_name` in `type_lookup` that defines the priority type (e.g., 'TaskPriority').
  - `{{TYPE_VALUES_PLACEHOLDER}}`: A comma-separated string of `type_value`s to remove.
- **Example Usage**:
  ```python
  priority_values = "'Low', 'Medium', 'High'"
  op.execute(load_cleanup_priority_references_template('task', 'priority', 'TaskPriority', priority_values))
  ```

## Adding New Templates

To add a new template:

1. Create a new `.sql` file in `templates/`
2. Use placeholders like `{{PLACEHOLDER_NAME}}`
3. Add a method to `template_loader.py`
4. Add examples to the README

## Benefits

- **DRY Principle**: Don't Repeat Yourself - SQL patterns are defined once
- **Consistency**: All data insertions follow the same pattern
- **Maintainability**: Changes to patterns only need to be made in templates
- **Reusability**: Easy to add new data types
- **Type Safety**: Python functions provide better error checking than raw SQL
- **Documentation**: Self-documenting through function names and parameters

## Migration from Hardcoded SQL

To migrate existing hardcoded SQL to use templates:

1. Identify the pattern (type_lookup or status)
2. Extract the data into a list of dictionaries
3. Replace hardcoded SQL with template function calls
4. Test the migration thoroughly
5. Update downgrade function to use cleanup templates

This template system makes database migrations more maintainable and reduces the chance of errors from copy-pasting SQL code.

# Database Models

## Overview

The Rhesis backend uses SQLAlchemy ORM to interact with the PostgreSQL database. All models are defined in the `app/models/` directory and inherit from a common `Base` class.

## Base Model

All models inherit from a common `Base` class that provides standard fields:

- `id`: UUID primary key
- `nano_id`: Human-readable unique identifier
- `created_at`: Timestamp for record creation
- `updated_at`: Timestamp that updates whenever the record is modified

## Core Models

### User

Represents a user in the system, with authentication and authorization details.

Key fields:
- `email`: User's email address (unique)
- `name`: User's display name
- `is_active`: Whether the user account is active
- `is_superuser`: Whether the user has admin privileges
- `organization_id`: Foreign key to the organization

### Organization

Represents a tenant organization in the multi-tenant architecture.

Key fields:
- `name`: Organization name
- `slug`: URL-friendly identifier
- `is_active`: Whether the organization is active

### Test

Represents an individual test case for AI model evaluation.

Key fields:
- `name`: Test name
- `description`: Test description
- `prompt_id`: Foreign key to the prompt

### TestSet

A collection of tests grouped for evaluation purposes.

Key fields:
- `name`: Test set name
- `description`: Test set description
- `organization_id`: Foreign key to the organization

### Prompt

Templates for inputs to AI models.

Key fields:
- `content`: The prompt text
- `name`: Prompt name
- `description`: Prompt description

### Model

Represents an AI model configuration.

Key fields:
- `name`: Model name
- `provider`: Model provider (e.g., OpenAI)
- `version`: Model version

## Relationships

The database schema includes various relationships between models:

### One-to-Many Relationships

- Organization → Users: An organization has many users
- User → Tests: A user creates many tests
- TestSet → Tests: A test set contains many tests

### Many-to-Many Relationships

- Tests ↔ Tags: Tests can have multiple tags
- Prompts ↔ Categories: Prompts can belong to multiple categories

## Row-Level Security

The database implements row-level security to enforce multi-tenancy:

- Each model with organization-specific data includes an `organization_id` field
- PostgreSQL policies filter data based on the current organization context
- Session variables (`app.current_organization` and `app.current_user`) control access

## Mixins

The application uses mixins to add common functionality to models:

### TagsMixin

Adds tagging capabilities to models:

```python
class TagsMixin:
    @declared_attr
    def tags(cls):
        return relationship(
            "Tag",
            secondary="taggeditem",
            primaryjoin=f"and_(TaggedItem.item_id == {cls.__name__}.id, "
                        f"TaggedItem.item_type == '{cls.__name__.lower()}')",
            secondaryjoin="TaggedItem.tag_id == Tag.id",
            viewonly=True,
        )
```

## Database Initialization

The database schema is created using SQLAlchemy's metadata:

```python
Base.metadata.create_all(bind=engine)
```

For schema migrations, the application uses Alembic, which is configured in the `alembic/` directory.

## UUID Primary Keys

The application uses UUID primary keys instead of sequential integers for better security and distribution in a multi-tenant environment. The custom `GUID` type extends PostgreSQL's UUID type. 
# User Settings

The User model includes a `user_settings` JSONB column that stores user preferences and configurations. This enables users to customize their experience and set default LLM models for different use cases.

## Schema Structure

```json
{
  "version": 1,
  "llm_defaults": {
    "generation": {
      "model_id": "uuid-of-model",
      "fallback_model_id": "uuid-of-fallback-model",
      "temperature": 0.7,
      "max_tokens": 2000
    },
    "evaluation": {
      "model_id": "uuid-of-model",
      "fallback_model_id": "uuid-of-fallback-model",
      "temperature": 0.3,
      "max_tokens": 1000
    }
  },
  "ui": {
    "theme": "light",
    "density": "comfortable",
    "sidebar_collapsed": false,
    "default_page_size": 25
  },
  "notifications": {
    "email": {
      "test_run_complete": true,
      "test_failures": true,
      "weekly_summary": false
    },
    "in_app": {
      "test_run_complete": true,
      "mentions": true
    }
  },
  "localization": {
    "language": "en",
    "timezone": "UTC",
    "date_format": "YYYY-MM-DD",
    "time_format": "24h"
  },
  "editor": {
    "default_model": "uuid-of-model",
    "auto_save": true,
    "show_line_numbers": true
  },
  "privacy": {
    "show_email": false,
    "show_activity": true
  }
}
```

## Usage Examples

### Accessing LLM Model Preferences

```python
from rhesis.backend.app.models import User

# Get user's preferred model for test generation
user = await get_user(db, user_id)
generation_model_id = user.get_generation_model_id()

if generation_model_id:
    model = await get_model(db, generation_model_id)
    # Use the model for generation
else:
    # Use system default
    model = await get_default_model(db, purpose="generation")
```

### Getting All Generation Settings

```python
# Get all generation-related settings (includes temperature, max_tokens, etc.)
generation_settings = user.get_generation_settings()
model_id = generation_settings.get("model_id")
temperature = generation_settings.get("temperature", 0.7)  # Default to 0.7
max_tokens = generation_settings.get("max_tokens")
```

### Updating User Settings

```python
# Update specific settings (deep merge)
user.update_settings({
    "llm_defaults": {
        "generation": {
            "model_id": str(new_model.id),
            "temperature": 0.8
        }
    }
})
await db.commit()
```

### Partial Updates

The `update_settings` method performs a deep merge, so you can update nested properties without replacing the entire structure:

```python
# Only update the theme, everything else remains unchanged
user.update_settings({
    "ui": {
        "theme": "dark"
    }
})
```

## API Endpoints

### Get User Settings

```http
GET /api/users/me
```

Response includes `user_settings` field with all preferences.

### Update User Settings

```http
PATCH /api/users/me/settings
Content-Type: application/json

{
  "llm_defaults": {
    "generation": {
      "model_id": "550e8400-e29b-41d4-a716-446655440000",
      "temperature": 0.7
    }
  }
}
```

## Validation

All settings are validated using Pydantic schemas:

- **LLMModelSettings**: Validates model IDs, temperature (0.0-2.0), max_tokens (>0)
- **UISettings**: Validates theme choices, page size (1-100)
- **NotificationSettings**: Validates boolean preferences
- And more...

See `rhesis.backend.app.schemas.user` for complete schema definitions.

## Default Values

When a new user is created, they receive default settings:

```json
{
  "version": 1,
  "llm_defaults": {
    "generation": {},
    "evaluation": {}
  }
}
```

All other fields are optional and will use application defaults if not specified.

## Schema Versioning

The `version` field enables future schema migrations. When updating the schema structure:

1. Increment the version number
2. Create a migration function to transform old settings to new format
3. Apply migration on first access after schema change

## Best Practices

1. **Always check for null/missing values**: Use `.get()` with defaults when accessing settings
2. **Use helper methods**: Prefer `user.get_generation_model_id()` over direct dictionary access
3. **Validate before saving**: Use Pydantic schemas to validate updates before applying
4. **Partial updates**: Use `update_settings()` for merging rather than replacing entire settings
5. **Default behavior**: Always have sensible defaults for when settings are not specified

## Example: Using in Generation Service

```python
async def generate_tests(
    db: Session,
    user: User,
    test_configuration: TestConfiguration,
    # ... other params
):
    # Get user's preferred model or fall back to system default
    model_id = user.get_generation_model_id()
    
    if model_id:
        model = await get_model_by_id(db, model_id)
        if not model:
            # User's preferred model not found, use system default
            model = await get_system_default_model(db, purpose="generation")
    else:
        model = await get_system_default_model(db, purpose="generation")
    
    # Get any temperature override from settings
    settings = user.get_generation_settings()
    temperature = settings.get("temperature") or model.default_temperature or 0.7
    
    # Use the model and settings for generation
    response = await generate(
        model=model,
        temperature=temperature,
        # ... other params
    )
    
    return response
```

## Migration

To apply the database migration:

```bash
cd apps/backend
source .venv/bin/activate
alembic upgrade head
```

This will add the `user_settings` column to the `user` table with default values for all existing users.


# User Settings

The User model includes a `user_settings` JSONB column that stores user preferences and configurations. This enables users to customize their experience and set default LLM models for different use cases.

## Schema Structure

```json
{
  "version": 1,
  "models": {
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

The User model provides a centralized `settings` property that returns a `UserSettingsManager` instance. This provides clean, typed access to all user preferences without cluttering the User model with individual getter/setter methods.

### Accessing Model Preferences

```python
from rhesis.backend.app.models import User

# Get user's preferred model for test generation
user = await get_user(db, user_id)
generation_model_id = user.settings.models.generation.model_id

if generation_model_id:
    model = await get_model(db, generation_model_id)
    # Use the model for generation
else:
    # Use system default
    model = await get_default_model(db, purpose="generation")

# Access evaluation model
eval_model_id = user.settings.models.evaluation.model_id

# Access model parameters
temperature = user.settings.models.generation.temperature
max_tokens = user.settings.models.generation.max_tokens
```

### Accessing Other Settings

```python
# UI Settings
theme = user.settings.ui.theme
page_size = user.settings.ui.default_page_size
sidebar_collapsed = user.settings.ui.sidebar_collapsed

# Notification Settings
email_prefs = user.settings.notifications.email
in_app_prefs = user.settings.notifications.in_app

# Localization
language = user.settings.localization.language
timezone = user.settings.localization.timezone

# Editor Settings
auto_save = user.settings.editor.auto_save
show_line_numbers = user.settings.editor.show_line_numbers

# Privacy Settings
show_email = user.settings.privacy.show_email
```

### Updating User Settings

```python
# Update specific settings (deep merge)
user.settings.update({
    "models": {
        "generation": {
            "model_id": str(new_model.id),
            "temperature": 0.8
        }
    }
})
# Persist changes to database
user.user_settings = user.settings.raw
await db.commit()
```

### Partial Updates

The `update` method performs a deep merge, so you can update nested properties without replacing the entire structure:

```python
# Only update the theme, everything else remains unchanged
user.settings.update({
    "ui": {
        "theme": "dark"
    }
})
user.user_settings = user.settings.raw
await db.commit()
```

### Getting All Settings for a Category

```python
# Get all generation settings as a dictionary
all_generation = user.settings.models.generation.all
# Returns: {"model_id": "...", "temperature": 0.7, "max_tokens": null}

# Access raw settings dictionary
raw_settings = user.settings.raw
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

1. **Use the centralized settings property**: Always access settings via `user.settings.models.generation.model_id` rather than directly accessing `user_settings` dictionary
2. **Handle None values**: Settings properties return `None` for missing values, so always provide defaults in your logic
3. **Validate before saving**: Use Pydantic schemas to validate updates before applying
4. **Partial updates**: Use `user.settings.update()` for merging rather than replacing entire settings
5. **Persist after updates**: Remember to sync back to the model: `user.user_settings = user.settings.raw` and commit
6. **Default behavior**: Always have sensible defaults for when settings are not specified

## Example: Using in Generation Service

```python
async def generate_tests(
    db: Session,
    user: User,
    test_configuration: TestConfiguration,
    # ... other params
):
    # Get user's preferred model or fall back to system default
    model_id = user.settings.models.generation.model_id
    
    if model_id:
        model = await get_model_by_id(db, model_id)
        if not model:
            # User's preferred model not found, use system default
            model = await get_system_default_model(db, purpose="generation")
    else:
        model = await get_system_default_model(db, purpose="generation")
    
    # Get any temperature override from settings
    temperature = (
        user.settings.models.generation.temperature 
        or model.default_temperature 
        or 0.7
    )
    
    # Get max_tokens if specified
    max_tokens = user.settings.models.generation.max_tokens
    
    # Use the model and settings for generation
    response = await generate(
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        # ... other params
    )
    
    return response
```

## Centralized Settings Manager

The `UserSettingsManager` class provides a clean, type-safe interface for accessing settings:

- **Organized by domain**: `user.settings.models`, `user.settings.ui`, etc.
- **Type conversion**: Automatically converts UUIDs from strings
- **Default handling**: Returns `None` for missing values (no KeyErrors)
- **Clean updates**: Deep merge support via `update()` method
- **No clutter**: Keeps the User model clean and focused

### Architecture Benefits

1. **Single Responsibility**: Settings logic is separate from the User model
2. **Discoverability**: IDE autocomplete works perfectly (`user.settings.models.generation...`)
3. **Type Safety**: Properties return proper types (UUID, int, float, bool, str)
4. **Maintainability**: Easy to add new settings categories without modifying User
5. **Testability**: Can test settings logic independently

### Adding New Settings

To add a new settings category:

1. Add the category to the default settings structure
2. Create a new accessor class (e.g., `NewCategoryAccessor`)
3. Add a property to `UserSettingsManager` that returns the accessor
4. Update documentation

Example:

```python
# In user_settings.py
class FeatureFlagsAccessor:
    def __init__(self, flags: dict):
        self._data = flags
    
    @property
    def experimental_mode(self) -> bool:
        return self._data.get("experimental_mode", False)

# In UserSettingsManager
@property
def feature_flags(self) -> FeatureFlagsAccessor:
    """Access feature flags."""
    return FeatureFlagsAccessor(self._data.get("feature_flags", {}))
```

## Migration

To apply the database migration:

```bash
cd apps/backend
source .venv/bin/activate
alembic upgrade head
```

This will add the `user_settings` column to the `user` table with default values for all existing users.


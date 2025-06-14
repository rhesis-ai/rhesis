# Notification System

This directory contains the refactored notification system for the Rhesis backend.

## Structure

```
notifications/
├── __init__.py                 # Main notifications module
├── README.md                   # This file
└── email/                      # Email notification system
    ├── __init__.py            # Email module exports
    ├── service.py             # Main EmailService orchestrator
    ├── smtp.py                # SMTP/SendGrid communication
    └── templates.py           # Template loading and rendering
```

## Architecture

The notification system is organized into focused, single-responsibility modules:

### 1. **EmailService** (`service.py`)
- Main orchestrator for email notifications
- Coordinates SMTP and template services
- Provides high-level methods for different email types:
  - `send_task_completion_email()` - Regular task completion notifications
  - `send_test_execution_summary_email()` - Rich test execution summaries

### 2. **SMTPService** (`smtp.py`)
- Handles low-level SMTP communication
- Manages SendGrid/SMTP configuration
- Provides SSL/TLS connection handling
- Includes comprehensive error handling and logging

### 3. **TemplateService** (`templates.py`)
- Loads email templates from the `templates/` directory
- Renders templates with dynamic content
- Provides separate methods for text and HTML rendering
- Handles conditional content (project info, test details, etc.)

## Usage

### Basic Import
```python
from rhesis.backend.notifications import email_service

# Send a task completion email
success = email_service.send_task_completion_email(
    recipient_email="user@example.com",
    recipient_name="John Doe",
    task_name="Data Processing",
    task_id="task-123",
    status="success"
)
```

### Test Execution Summary
```python
# Send a rich test execution summary
success = email_service.send_test_execution_summary_email(
    recipient_email="user@example.com",
    recipient_name="John Doe",
    task_name="API Test Suite",
    task_id="task-456",
    status="partial",
    total_tests=10,
    tests_passed=8,
    tests_failed=2,
    test_set_name="Production API Tests",
    endpoint_name="User API",
    endpoint_url="https://api.example.com",
    project_name="My Project"
)
```

## Migration from Old System

The old monolithic `EmailService` in `tasks/email_service.py` has been refactored into this modular system. A backward compatibility module is provided at the old location to ensure existing imports continue to work, but will issue deprecation warnings.

### Old Import (deprecated)
```python
from rhesis.backend.tasks.email_service import email_service  # Issues warning
```

### New Import (recommended)
```python
from rhesis.backend.notifications import email_service
```

## Benefits of Refactoring

1. **Separation of Concerns**: Each module has a single, clear responsibility
2. **Maintainability**: Easier to modify SMTP, templates, or orchestration logic independently
3. **Testability**: Each component can be unit tested in isolation
4. **Extensibility**: Easy to add new notification types (SMS, Slack, etc.)
5. **Readability**: Smaller, focused files are easier to understand and navigate

## Configuration

The system uses the same environment variables as before:
- `SMTP_HOST` - SMTP server hostname
- `SMTP_PORT` - SMTP server port (default: 587)
- `SMTP_USER` - SMTP username
- `SMTP_PASSWORD` - SMTP password
- `FROM_EMAIL` - Sender email address

## Templates

Email templates are still located in `apps/backend/src/rhesis/backend/templates/`:
- `email_task_completion.txt` / `.html` - Regular task completion emails
- `email_test_execution_summary.txt` / `.html` - Test execution summary emails
- `email_fragments.py` - Reusable template components 
# Email Notification System

A centralized email notification system for the Rhesis backend using Jinja2 templates and SMTP.

## Features

- **Centralized Template System**: Use `EmailTemplate` enum and single `send_email()` method
- **Automatic Variable Handling**: Missing variables are automatically set to "N/A"
- **Template Discovery**: Get required variables for any template with `get_template_variables()`
- **Rich HTML Templates**: Beautiful, responsive email templates with conditional content
- **SMTP Integration**: Robust SMTP handling with SendGrid support

## Quick Start

```python
from rhesis.backend.notifications import email_service, EmailTemplate

# Send an email using the centralized approach
success = email_service.send_email(
    template=EmailTemplate.TASK_COMPLETION,
    recipient_email="user@example.com",
    subject="Your Task Completed Successfully",
    template_variables={
        'recipient_name': "John Doe",
        'task_name': "API Test Suite",
        'task_id': "task_12345",
        'status': "success",
        'execution_time': "2 minutes 30 seconds"
        # Missing variables will be set to "N/A" automatically
    },
    task_id="task_12345"
)
```

## Available Templates

### EmailTemplate.TASK_COMPLETION
For general task completion notifications.

**Required Variables:**
- `recipient_name`, `task_name`, `task_id`, `status`, `completed_at`
- `execution_time`, `error_message`, `test_run_id`, `frontend_url`

### EmailTemplate.TEST_EXECUTION_SUMMARY
For test execution summary notifications.

**Required Variables:**
- `recipient_name`, `task_name`, `task_id`, `status`, `completed_at`
- `total_tests`, `tests_passed`, `tests_failed`, `execution_time`
- `test_run_id`, `status_details`, `frontend_url`, `test_set_name`
- `endpoint_name`, `endpoint_url`, `project_name`

## Template Discovery

```python
# Get required variables for a template
required_vars = email_service.get_template_variables(EmailTemplate.TASK_COMPLETION)
print(f"Required variables: {required_vars}")

# List all available templates
for template in EmailTemplate:
    print(f"{template.name}: {template.value}")
```

## Adding New Templates

1. **Create Template File**: Add a new `.jinja2` file in `templates/`
2. **Update Enum**: Add entry to `EmailTemplate` enum
3. **Define Variables**: Add required variables to `template_variables` dict in `TemplateService`

Example:
```python
class EmailTemplate(Enum):
    TASK_COMPLETION = "task_completion.html.jinja2"
    TEST_EXECUTION_SUMMARY = "test_execution_summary.html.jinja2"
    NEW_TEMPLATE = "new_template.html.jinja2"  # Add this

# In TemplateService.__init__():
self.template_variables = {
    # ... existing templates ...
    EmailTemplate.NEW_TEMPLATE: {
        'recipient_name', 'message', 'timestamp'  # Define required vars
    }
}
```

## Configuration

Email service requires these environment variables:
- `SMTP_HOST`: SMTP server hostname
- `SMTP_PORT`: SMTP server port (465 for SSL, 587 for TLS)
- `SMTP_USER`: SMTP username
- `SMTP_PASSWORD`: SMTP password
- `FROM_EMAIL`: Sender email address (defaults to `"Harry from Rhesis AI" <engineering@rhesis.ai>`)
- `WELCOME_FROM_EMAIL`: Optional sender for welcome emails (e.g., `"Nicolai from Rhesis AI" <hello@rhesis.ai>`)

**Note**: When including a sender name with spaces, wrap it in quotes: `"Sender Name" <email@domain.com>`

## Architecture

```
notifications/email/
├── service.py              # EmailService - main orchestrator
├── smtp.py                 # SMTPService - SMTP handling
├── template_service.py     # TemplateService - Jinja2 rendering
└── templates/
    ├── task_completion.html.jinja2
    └── test_execution_summary.html.jinja2
```

## Benefits

- **Scalable**: Easy to add new templates without code changes
- **Maintainable**: Single method for all email types
- **Robust**: Automatic handling of missing variables
- **Developer Friendly**: Template discovery and clear error messages
- **Future Proof**: Centralized system ready for any email template

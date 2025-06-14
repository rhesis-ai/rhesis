# Email Notification System

## Overview

The Rhesis backend includes an automated email notification system that sends notifications to users when their background tasks complete. This system integrates with the Celery task system and can use any SMTP provider, including SendGrid.

## Features

- 📧 **Automatic notifications**: Users receive emails when their tasks complete successfully or fail
- 🎨 **Rich HTML emails**: Professional-looking emails with both HTML and plain text versions
- 🔗 **Direct links**: Clickable links to view results in the frontend application
- 🏢 **Multi-tenant aware**: Respects organization and user context
- 🛡️ **Error handling**: Graceful degradation if email service is unavailable
- ⚡ **Performance**: Email sending doesn't block task execution

## Configuration

### Environment Variables

The following environment variables must be configured in the worker deployment:

```bash
# SMTP Configuration (e.g., SendGrid)
SMTP_HOST=smtp.sendgrid.net
SMTP_PORT=587
SMTP_USER=apikey
SMTP_PASSWORD=your_sendgrid_api_key

# Frontend URL for generating links
FRONTEND_URL=https://app.rhesis.ai
```

### SendGrid Setup

For SendGrid specifically:

1. Create a SendGrid account and verify your sender domain
2. Generate an API key with "Mail Send" permissions
3. Use these settings:
   - `SMTP_HOST`: `smtp.sendgrid.net`
   - `SMTP_PORT`: `587`
   - `SMTP_USER`: `apikey`
   - `SMTP_PASSWORD`: Your SendGrid API key

### Other SMTP Providers

The system works with any SMTP provider. Common configurations:

```bash
# Gmail SMTP
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password

# AWS SES
SMTP_HOST=email-smtp.us-east-1.amazonaws.com
SMTP_PORT=587
SMTP_USER=your-ses-smtp-username
SMTP_PASSWORD=your-ses-smtp-password

# Mailgun
SMTP_HOST=smtp.mailgun.org
SMTP_PORT=587
SMTP_USER=your-mailgun-smtp-login
SMTP_PASSWORD=your-mailgun-smtp-password
```

## How It Works

### Selective Email Notifications

**Important:** Email notifications are now **opt-in** using the `@email_notification` decorator to prevent spam when running parallel tasks. Only tasks that explicitly use the decorator will send email notifications.

### Email Notification Decorator

#### Using the `@email_notification` Decorator

The new decorator approach provides fine-grained control over email notifications:

```python
from rhesis.backend.tasks.base import BaseTask, with_tenant_context, email_notification
from rhesis.backend.notifications.email.template_service import EmailTemplate
from rhesis.backend.worker import app

@email_notification(
    template=EmailTemplate.TASK_COMPLETION,
    subject_template="Task Complete: {task_name} - {status.title()}"
)
@app.task(base=BaseTask, name="your.user.facing.task", bind=True)
@with_tenant_context
def user_facing_task(self, params, db=None):
    """This task will send email notifications using the specified template."""
    # Your task logic here
    return {"result": "success", "test_run_id": "optional-for-links"}
```

#### Available Email Templates

```python
from rhesis.backend.notifications.email.template_service import EmailTemplate

# For general task completion
@email_notification(template=EmailTemplate.TASK_COMPLETION)

# For test execution summaries with detailed results
@email_notification(template=EmailTemplate.TEST_EXECUTION_SUMMARY)
```

#### Custom Subject Templates

You can customize the email subject using template variables:

```python
@email_notification(
    template=EmailTemplate.TEST_EXECUTION_SUMMARY,
    subject_template="Test Execution Complete: {test_set_name} - {status.title()}"
)
```

### Task Types

#### 1. **Tasks with Email Notifications** - Using Decorator
Use the decorator for tasks that users directly submit and want to be notified about:

```python
from rhesis.backend.tasks.base import BaseTask, with_tenant_context, email_notification
from rhesis.backend.notifications.email.template_service import EmailTemplate
from rhesis.backend.worker import app

@email_notification(
    template=EmailTemplate.TASK_COMPLETION,
    subject_template="Task Complete: {task_name} - {status.title()}"
)
@app.task(base=BaseTask, name="your.user.facing.task", bind=True)
@with_tenant_context
def user_facing_task(self, params, db=None):
    """This task will send email notifications on completion."""
    # Your task logic here
    return {"result": "success", "test_run_id": "optional-for-links"}
```

#### 2. **Silent Tasks** - No Decorator
Tasks without the decorator will not send email notifications:

```python
from rhesis.backend.tasks.base import BaseTask, with_tenant_context
from rhesis.backend.worker import app

@app.task(base=BaseTask, name="your.background.task", bind=True)
@with_tenant_context  
def background_task(self, params, db=None):
    """This task will NOT send email notifications."""
    # Your parallel task logic here
    return {"result": "success"}
```

#### 3. **Legacy EmailEnabledTask** - Still Supported
The old `EmailEnabledTask` is still supported for backward compatibility:

```python
from rhesis.backend.tasks.base import EmailEnabledTask, with_tenant_context
from rhesis.backend.worker import app

@app.task(base=EmailEnabledTask, name="your.legacy.task", bind=True)
@with_tenant_context
def legacy_task(self, params, db=None):
    """This task will send basic task completion emails."""
    # Your task logic here
    return {"result": "success"}
```

### Chord Example

When running tasks in parallel with chords, use the decorator appropriately:

```python
from celery import chord

# These run in parallel - no emails needed (no decorator)
parallel_tasks = [
    background_task.s(param1),
    background_task.s(param2),
    background_task.s(param3),
]

# This is the callback when all parallel tasks complete - send email
@email_notification(template=EmailTemplate.TEST_EXECUTION_SUMMARY)
@app.task(base=BaseTask, bind=True)
def collect_results_task(self, results):
    # Process results and return summary
    return {"total_tests": 10, "tests_passed": 8, "tests_failed": 2}

callback = collect_results_task.s()

# Execute: parallel tasks run silently, only callback sends email
result = chord(parallel_tasks)(callback)
```

### Current Task Configuration

- ✅ **`collect_results`** - Uses `@email_notification(template=EmailTemplate.TEST_EXECUTION_SUMMARY)` (sends detailed test summaries)
- ✅ **`email_notification_test`** - Uses `@email_notification(template=EmailTemplate.TASK_COMPLETION)` (sends basic completion emails)  
- ✅ **Individual test execution tasks** - No decorator (no emails)
- ✅ **Utility tasks** - No decorator (no emails)

### Automatic Integration

When a task with the `@email_notification` decorator completes (either successfully or fails permanently), the system:

1. **Retrieves user information** from the task context
2. **Skips placeholder emails** (internal system users)
3. **Calculates execution time** if available
4. **Uses the specified template** to generate email content
5. **Applies template variables** from task results and context
6. **Sends HTML email** using the centralized email service
7. **Logs the outcome** without failing the task

### Template Variables

The decorator automatically provides these variables to templates:

- `recipient_name`: User's display name
- `task_name`: Human-readable task name
- `task_id`: Unique task identifier
- `status`: Task completion status ('success' or 'failed')
- `execution_time`: Formatted execution duration
- `error_message`: Error details (for failed tasks)
- `frontend_url`: Base URL for links
- `completed_at`: Completion timestamp

Additional variables can be provided by returning them from the task:

```python
@email_notification(template=EmailTemplate.TEST_EXECUTION_SUMMARY)
@app.task(base=BaseTask, bind=True)
def test_task(self):
    # Task logic here
    return {
        'total_tests': 10,
        'tests_passed': 8,
        'tests_failed': 2,
        'test_set_name': 'API Tests',
        'project_name': 'My Project'
    }
```

### Task Integration

```python
from rhesis.backend.tasks.base import BaseTask, with_tenant_context, email_notification
from rhesis.backend.notifications.email.template_service import EmailTemplate
from rhesis.backend.worker import app

@email_notification(
    template=EmailTemplate.TASK_COMPLETION,
    subject_template="Task Complete: {task_name} - {status.title()}"
)
@app.task(base=BaseTask, name="your.task.name", bind=True)
@with_tenant_context
def your_task(self, your_params, db=None):
    """Your task automatically gets email notifications."""
    # Your task logic here
    return {"result": "success", "test_run_id": "optional-for-links"}
```

## Email Service Architecture

### EmailService Class

The core `EmailService` class in `tasks/email_service.py` handles:

```python
class EmailService:
    def __init__(self):
        # Loads SMTP configuration from environment
        # Validates configuration completeness
        
    def send_task_completion_email(
        self, 
        recipient_email: str,
        recipient_name: Optional[str],
        task_name: str,
        task_id: str,
        status: str,
        execution_time: Optional[str] = None,
        error_message: Optional[str] = None,
        test_run_id: Optional[str] = None,
        frontend_url: Optional[str] = None
    ) -> bool:
        # Sends HTML and plain text email
        # Returns success/failure status
```

### BaseTask Integration

The `BaseTask` class includes:

- `_get_user_info()`: Retrieves user email and name from database
- `_send_task_completion_email()`: Handles email sending with error handling
- `on_success()`: Sends success notifications
- `on_failure()`: Sends failure notifications (only for permanent failures)

## User Experience

### What Users Receive

When users submit tasks through the API (e.g., test configurations), they automatically receive:

1. **Immediate API response** with task ID
2. **Email notification** when the task completes with:
   - Clear status indication
   - Task details and timing
   - Direct link to results (if applicable)
   - Professional branding

### Email Examples

#### Success Email
```
Subject: Task Completed: Execute Test Configuration - Success

✅ Task Completed

Hello John Doe,

Your task has completed with status: SUCCESS

Task Details:
- Task Name: Execute Test Configuration
- Task ID: 12345678-1234-5678-9012-123456789012
- Status: Success
- Completed at: 2024-01-15 14:30:25 UTC
- Execution Time: 2m 45s
- Test Run ID: abcd1234-5678-9012-efgh-567890123456

[View Results]

Best regards,
Rhesis AI Team
```

## Testing

### Test Endpoint

Use the test endpoint to verify email functionality:

```bash
POST /api/tasks/email-notification-test
Authorization: Bearer <your-token>
Content-Type: application/json

{
  "message": "Testing email notifications"
}
```

### Manual Testing

```python
# In your development environment
from rhesis.backend.tasks.email_service import email_service

success = email_service.send_task_completion_email(
    recipient_email="test@example.com",
    recipient_name="Test User",
    task_name="Test Task",
    task_id="test-123",
    status="success",
    frontend_url="https://app.rhesis.ai"
)
print(f"Email sent: {success}")
```

## Troubleshooting

### Common Issues

#### No Emails Being Sent

1. **Check SMTP configuration**:
   ```bash
   # In worker logs, look for:
   "SMTP configuration incomplete. Email notifications will be disabled."
   ```

2. **Verify environment variables**:
   ```bash
   kubectl exec -it deployment/rhesis-worker -- env | grep SMTP
   ```

3. **Check user emails**:
   - Ensure users have valid email addresses
   - System skips placeholder emails (`*@placeholder.rhesis.ai`)

#### SMTP Authentication Errors

1. **Verify credentials**:
   - Double-check SMTP username and password
   - For SendGrid, ensure you're using `apikey` as username

2. **Check firewall/network**:
   - Ensure port 587 is accessible from worker pods
   - Some networks block SMTP ports

#### Email Content Issues

1. **Missing links**:
   - Verify `FRONTEND_URL` is set correctly
   - Check that `test_run_id` is included in task results

2. **Formatting problems**:
   - Check logs for email generation errors
   - Verify HTML content in email client

### Monitoring

Monitor email notifications through:

1. **Worker logs**:
   ```bash
   kubectl logs deployment/rhesis-worker | grep "email"
   ```

2. **Success indicators**:
   ```
   Task completion email sent successfully to user@example.com for task 12345
   ```

3. **Error indicators**:
   ```
   Failed to send task completion email to user@example.com: SMTP error
   ```

## Security Considerations

### Email Content
- **No sensitive data**: Task results are not included in emails
- **Secure links**: Frontend URLs use HTTPS
- **User privacy**: Only the task owner receives notifications

### SMTP Security
- **TLS encryption**: All SMTP connections use STARTTLS
- **Credential protection**: SMTP passwords stored as Kubernetes secrets
- **Network security**: SMTP traffic encrypted in transit

### Access Control
- **User context**: Emails only sent to the user who submitted the task
- **Organization isolation**: Multi-tenant architecture prevents cross-organization emails

## Future Enhancements

Potential improvements to consider:

- **Email preferences**: Allow users to opt-out of notifications
- **Notification types**: Different notifications for different task types
- **Email templates**: Customizable email templates per organization
- **Delivery status**: Track email delivery and bounce handling
- **Digest emails**: Summary emails for multiple completed tasks
- **Mobile optimization**: Enhanced mobile email experience

## Deployment

### Worker Deployment

Ensure your worker deployment includes the SMTP environment variables:

```yaml
# apps/worker/k8s/deployment.yaml
env:
- name: SMTP_HOST
  valueFrom:
    secretKeyRef:
      name: rhesis-worker-secrets
      key: SMTP_HOST
- name: SMTP_PORT
  valueFrom:
    secretKeyRef:
      name: rhesis-worker-secrets
      key: SMTP_PORT
- name: SMTP_USER
  valueFrom:
    secretKeyRef:
      name: rhesis-worker-secrets
      key: SMTP_USER
- name: SMTP_PASSWORD
  valueFrom:
    secretKeyRef:
      name: rhesis-worker-secrets
      key: SMTP_PASSWORD
- name: FRONTEND_URL
  valueFrom:
    secretKeyRef:
      name: rhesis-worker-secrets
      key: FRONTEND_URL
```

### CI/CD Pipeline

The GitHub Actions workflow automatically includes SMTP secrets:

```yaml
# .github/workflows/worker.yml
--from-literal=SMTP_HOST="${{ secrets.SMTP_HOST }}" \
--from-literal=SMTP_PORT="${{ secrets.SMTP_PORT }}" \
--from-literal=SMTP_USER="${{ secrets.SMTP_USER }}" \
--from-literal=SMTP_PASSWORD="${{ secrets.SMTP_PASSWORD }}" \
--from-literal=FRONTEND_URL="${{ secrets.FRONTEND_URL }}" \
```

Remember to set these secrets in your GitHub repository settings for each environment (dev, stg, prd). 
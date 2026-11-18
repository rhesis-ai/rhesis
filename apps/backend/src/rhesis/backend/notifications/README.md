# Notifications

Outbound notifications for the Rhesis backend. Email is the only channel today.

```python
from rhesis.backend.notifications import EmailTemplate, email_service

email_service.send_email(
    template=EmailTemplate.TASK_COMPLETION,
    recipient_email="user@example.com",
    subject="Your task completed",
    template_variables={"task_name": "API Test Suite", "status": "success"},
)
```

- `email/README.md` covers the templates, their variables, configuration and how to add a template.
- `docs/content/contribute/backend/email-notifications.mdx` covers how jobs send emails with
  `@email_notification`.

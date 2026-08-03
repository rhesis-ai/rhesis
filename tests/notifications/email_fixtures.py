"""Sample payloads for every email template.

Shared by tests/notifications/test_email_brand.py and
apps/backend/scripts/preview_emails.py so the previews and the brand assertions
always exercise the same data. Values are deliberately long in places (names,
task titles, URLs) to shake out wrapping problems at 375px.
"""

from datetime import datetime, timezone

from rhesis.backend.notifications.email.template_service import EmailTemplate

FRONTEND = "https://app.rhesis.ai"
NOW = datetime(2026, 8, 3, 14, 30, tzinfo=timezone.utc)

# One fixture per template. Values are deliberately long in places (names,
# task titles, URLs) to shake out wrapping problems at 375px.
FIXTURES: dict[EmailTemplate, dict] = {
    EmailTemplate.WELCOME: {
        "recipient_name": "Alex Nguyen",
        "recipient_email": "alex@example.com",
        "frontend_url": FRONTEND,
        "calendar_link": "https://cal.com/rhesis/intro",
    },
    EmailTemplate.EMAIL_VERIFICATION: {
        "recipient_name": "Alex",
        "verification_url": (
            f"{FRONTEND}/auth/verify-email"
            "?token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.longish-token-value"
        ),
    },
    EmailTemplate.PASSWORD_RESET: {
        "recipient_name": "Alex",
        "reset_url": (
            f"{FRONTEND}/auth/reset-password"
            "?token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.longish-token-value"
        ),
    },
    EmailTemplate.MAGIC_LINK: {
        "recipient_name": "Alex",
        "magic_link_url": (
            f"{FRONTEND}/auth/magic?token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.longish"
        ),
        "is_new_user": False,
    },
    EmailTemplate.MIGRATION_PASSWORD_SETUP: {
        "recipient_name": "Alex",
        "reset_url": f"{FRONTEND}/auth/reset-password?token=migration-token-value",
    },
    EmailTemplate.TEAM_INVITATION: {
        "recipient_name": "Alex Nguyen",
        "recipient_email": "alex@example.com",
        "organization_name": "Northwind Health Analytics",
        "organization_website": "https://northwind.example.com",
        "inviter_name": "Priya Raman",
        "inviter_email": "priya@northwind.example.com",
        "frontend_url": FRONTEND,
    },
    EmailTemplate.TASK_ASSIGNMENT: {
        "assignee_name": "Alex Nguyen",
        "assigner_name": "Priya Raman",
        "task_title": "Review the refusal-rate regression on the triage assistant",
        "task_description": (
            "The nightly run shows refusals up 12 points on the German prompts. "
            "Check whether the system prompt change from Tuesday is responsible."
        ),
        "task_id": "8f2c1e94-7b3a-4d21-9c8e-1a2b3c4d5e6f",
        "status_name": "In Progress",
        "priority_name": "High",
        "entity_type": "TestRun",
        "entity_id": "3a1b2c3d-4e5f-6071-8293-a4b5c6d7e8f9",
        "entity_name": "Triage assistant · nightly",
        "created_at": NOW,
        "task_metadata": None,
        "frontend_url": FRONTEND,
    },
    EmailTemplate.TASK_COMPLETION: {
        "recipient_name": "Alex",
        "task_name": "Generate adversarial test set",
        "task_id": "8f2c1e94-7b3a-4d21-9c8e-1a2b3c4d5e6f",
        "status": "SUCCESS",
        "completed_at": NOW,
        "execution_time": "4m 12s",
        "error_message": None,
        "frontend_url": FRONTEND,
        "test_set_id": "11112222-3333-4444-5555-666677778888",
    },
    EmailTemplate.TEST_EXECUTION_SUMMARY: {
        "recipient_name": "Alex",
        "task_name": "Triage assistant · nightly regression",
        "task_id": "8f2c1e94-7b3a-4d21-9c8e-1a2b3c4d5e6f",
        "status": "partial",
        "execution_status": "Partial",
        "completed_at": NOW,
        "total_tests": 248,
        "tests_passed": 231,
        "tests_failed": 14,
        "execution_errors": 3,
        "execution_time": "11m 48s",
        "test_run_id": "3a1b2c3d-4e5f-6071-8293-a4b5c6d7e8f9",
        "status_details": (
            "14 tests failed on the German prompt set and 3 could not reach the endpoint."
        ),
        "frontend_url": FRONTEND,
        "test_set_name": "Adversarial · healthcare triage",
        "endpoint_name": "triage-assistant-staging",
        "endpoint_url": "https://staging.northwind.example.com/v1/triage",
        "project_name": "Northwind Triage",
    },
    EmailTemplate.FEEDBACK: {
        "user_name": "Alex Nguyen",
        "user_email": "alex@example.com",
        "feedback": (
            "The explorer view is great, but I'd love to filter by metric score.\n\n"
            "Also: the export button is easy to miss."
        ),
        "rating": 4,
    },
    EmailTemplate.POLYPHEMUS_ACCESS_REQUEST: {
        "user_name": "Alex Nguyen",
        "user_email": "alex@example.com",
        "user_id": "99998888-7777-6666-5555-444433332222",
        "organization_name": "Northwind Health Analytics",
        "organization_display_name": "Northwind Health",
        "organization_email": "ops@northwind.example.com",
        "organization_website": "https://northwind.example.com",
        "organization_is_active": True,
        "expected_monthly_requests": 25000,
        "request_timestamp": "2026-08-03 14:30:00 UTC",
        "justification": (
            "We're red-teaming a clinical triage assistant ahead of a September rollout "
            "and need adversarial coverage on the German prompt set."
        ),
    },
}

# Extra passes worth looking at because they take a different branch.
VARIANTS: list[tuple[str, EmailTemplate, dict]] = [
    (
        "magic_link__new_user",
        EmailTemplate.MAGIC_LINK,
        {**FIXTURES[EmailTemplate.MAGIC_LINK], "is_new_user": True},
    ),
    (
        "test_execution_summary__all_passed",
        EmailTemplate.TEST_EXECUTION_SUMMARY,
        {
            **FIXTURES[EmailTemplate.TEST_EXECUTION_SUMMARY],
            "status": "success",
            "execution_status": "Complete",
            "total_tests": 248,
            "tests_passed": 248,
            "tests_failed": 0,
            "execution_errors": 0,
            "status_details": "All tests passed.",
        },
    ),
    (
        "test_execution_summary__failed",
        EmailTemplate.TEST_EXECUTION_SUMMARY,
        {
            **FIXTURES[EmailTemplate.TEST_EXECUTION_SUMMARY],
            "status": "failure",
            "execution_status": "Failed",
            "tests_passed": 0,
            "tests_failed": 248,
            "execution_errors": 0,
            "status_details": "The endpoint returned 502 for every request.",
        },
    ),
    (
        "task_completion__failed",
        EmailTemplate.TASK_COMPLETION,
        {
            **FIXTURES[EmailTemplate.TASK_COMPLETION],
            "status": "FAILURE",
            "error_message": "TimeoutError: the generation model did not respond within 300s",
        },
    ),
]

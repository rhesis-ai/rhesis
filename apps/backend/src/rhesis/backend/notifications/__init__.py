"""
Notification system for Rhesis backend.

This module provides various notification mechanisms including email notifications
for task completions, test execution summaries, and other system events.
"""

from rhesis.backend.notifications.email.service import EmailService
from rhesis.backend.notifications.email.template_service import EmailTemplate

# Global email service instance
email_service = EmailService()

__all__ = [
    'email_service',
    'EmailService',
    'EmailTemplate'
] 
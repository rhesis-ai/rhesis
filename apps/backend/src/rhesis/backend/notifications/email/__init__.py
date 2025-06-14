"""
Email notification module for sending HTML emails via SMTP.

This module provides a centralized email service with template-based rendering.
"""

from .service import EmailService
from .template_service import EmailTemplate, TemplateService
from .smtp import SMTPService

# Main service for sending emails
email_service = EmailService()

# Export the main components
__all__ = [
    'EmailService',
    'EmailTemplate', 
    'TemplateService',
    'SMTPService',
    'email_service'
] 
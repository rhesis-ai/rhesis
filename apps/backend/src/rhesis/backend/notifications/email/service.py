"""
Main email service that orchestrates SMTP and template services.
"""

import os
import re
from email.mime.text import MIMEText
from typing import Any, Dict, List, Optional

from rhesis.backend.logging.rhesis_logger import logger

from .smtp import SMTPService
from .template_service import EmailTemplate, TemplateService


class EmailService:
    """Main email service for sending HTML notifications."""

    # List of regex patterns for email addresses that should not receive welcome emails
    WELCOME_EMAIL_EXCLUSION_PATTERNS: List[str] = [
        r"new_user_",  # Exclude test users with new_user_ prefix
        # Add more patterns here as needed, e.g.:
        # r"test@",
        # r".*@example\.com$",
    ]

    def __init__(self):
        self.smtp_service = SMTPService()
        self.template_service = TemplateService()

    @property
    def is_configured(self) -> bool:
        """Check if email service is properly configured."""
        return self.smtp_service.is_configured

    def _should_exclude_from_welcome_email(self, email: str) -> bool:
        """
        Check if an email address matches any exclusion pattern.

        Args:
            email: The email address to check

        Returns:
            bool: True if the email should be excluded, False otherwise
        """
        for pattern in self.WELCOME_EMAIL_EXCLUSION_PATTERNS:
            if re.search(pattern, email):
                logger.info(
                    f"Email {email} matched exclusion pattern '{pattern}', skipping welcome email"
                )
                return True
        return False

    def send_email(
        self,
        template: EmailTemplate,
        recipient_email: str,
        subject: str,
        template_variables: Dict[str, Any],
        task_id: Optional[str] = None,
        from_email: Optional[str] = None,
        bcc: Optional[str] = None,
    ) -> bool:
        """
        Send an email using the specified template.

        Args:
            template: The email template to use
            recipient_email: Email address to send to
            subject: Email subject line
            template_variables: Variables to pass to the template
            task_id: Optional task ID for logging purposes
            from_email: Optional custom from email address (overrides default)
            bcc: Optional BCC email address

        Returns:
            bool: True if email was sent successfully, False otherwise
        """
        if not self.is_configured:
            logger.warning(f"Cannot send email to {recipient_email}: SMTP not configured")
            return False

        logger.info(f"Starting email to {recipient_email} using template {template.value}")

        try:
            # Render the template
            html_content = self.template_service.render_template(template, template_variables)

            # Create HTML message
            msg = MIMEText(html_content, "html")
            msg["Subject"] = subject
            msg["From"] = from_email if from_email else self.smtp_service.from_email
            msg["To"] = recipient_email

            logger.debug(f"Created HTML email message with subject: {msg['Subject']}")
            logger.debug(f"HTML content length: {len(html_content)}")

            # Send email using SMTP service
            return self.smtp_service.send_message(
                msg, recipient_email, task_id or "generic", bcc=bcc
            )

        except Exception as e:
            logger.error(f"Failed to send email to {recipient_email}: {str(e)}")
            logger.error(f"Error type: {type(e).__name__}")
            import traceback

            logger.error(f"Traceback: {traceback.format_exc()}")
            return False

    def get_template_variables(self, template: EmailTemplate) -> set:
        """
        Get the list of variables required by a template.

        Args:
            template: The email template

        Returns:
            set: Set of variable names required by the template
        """
        return self.template_service.get_template_variables(template)

    def send_team_invitation_email(
        self,
        recipient_email: str,
        recipient_name: Optional[str],
        organization_name: str,
        organization_website: Optional[str],
        inviter_name: str,
        inviter_email: str,
        frontend_url: Optional[str] = None,
    ) -> bool:
        """
        Send a team invitation email to a new user.

        Args:
            recipient_email: Email address of the person being invited
            recipient_name: Name of the person being invited (optional)
            organization_name: Name of the organization they're being invited to
            organization_website: Website of the organization (optional)
            inviter_name: Name of the person sending the invitation
            inviter_email: Email of the person sending the invitation
            frontend_url: URL to the frontend application

        Returns:
            bool: True if email was sent successfully, False otherwise
        """
        if not self.is_configured:
            logger.warning(
                f"Cannot send invitation email to {recipient_email}: SMTP not configured"
            )
            return False

        # Set default frontend URL if not provided
        if not frontend_url:
            frontend_url = os.getenv("FRONTEND_URL", "https://app.rhesis.ai")

        subject = f"You're invited to join {organization_name} on Rhesis AI!"

        template_variables = {
            "recipient_email": recipient_email,
            "recipient_name": recipient_name or "",
            "organization_name": organization_name,
            "organization_website": organization_website or "",
            "inviter_name": inviter_name,
            "inviter_email": inviter_email,
            "frontend_url": frontend_url,
        }

        return self.send_email(
            template=EmailTemplate.TEAM_INVITATION,
            recipient_email=recipient_email,
            subject=subject,
            template_variables=template_variables,
            task_id="team_invitation",
        )

    def send_welcome_email(
        self,
        recipient_email: str,
        recipient_name: Optional[str],
        frontend_url: Optional[str] = None,
        calendar_link: Optional[str] = None,
    ) -> bool:
        """
        Send a welcome email to a new user.

        Args:
            recipient_email: Email address of the new user
            recipient_name: Name of the new user (optional)
            frontend_url: URL to the frontend application
            calendar_link: URL to book a call with the founder

        Returns:
            bool: True if email was sent successfully, False otherwise
        """
        if not self.is_configured:
            logger.warning(f"Cannot send welcome email to {recipient_email}: SMTP not configured")
            return False

        # Set default URLs if not provided
        if not frontend_url:
            frontend_url = os.getenv("FRONTEND_URL", "https://app.rhesis.ai")

        if not calendar_link:
            calendar_link = os.getenv("WELCOME_CALENDAR_LINK")

        # Get BCC email from environment variable (optional)
        bcc_email = os.getenv("AGENT_EMAIL_BCC")

        # Get welcome-specific from email (defaults to hello@rhesis.ai for founder emails)
        welcome_from_email = os.getenv(
            "WELCOME_FROM_EMAIL", '"Nicolai from Rhesis AI" <hello@rhesis.ai>'
        )

        subject = "Welcome to Rhesis AI!"

        template_variables = {
            "recipient_name": recipient_name or "",
            "recipient_email": recipient_email,
            "frontend_url": frontend_url,
            "calendar_link": calendar_link,
        }

        # Check if email should be excluded based on patterns
        if self._should_exclude_from_welcome_email(recipient_email):
            return False

        return self.send_email(
            template=EmailTemplate.WELCOME,
            recipient_email=recipient_email,
            subject=subject,
            template_variables=template_variables,
            task_id="welcome",
            from_email=welcome_from_email,
            bcc=bcc_email,
        )

    def send_verification_email(
        self,
        recipient_email: str,
        recipient_name: Optional[str],
        verification_url: str,
    ) -> bool:
        """Send an email verification link to a user."""
        if not self.is_configured:
            logger.warning(
                f"Cannot send verification email to {recipient_email}: SMTP not configured"
            )
            return False

        return self.send_email(
            template=EmailTemplate.EMAIL_VERIFICATION,
            recipient_email=recipient_email,
            subject="Verify your email - Rhesis AI",
            template_variables={
                "recipient_name": recipient_name or "",
                "verification_url": verification_url,
            },
            task_id="email_verification",
        )

    def send_password_reset_email(
        self,
        recipient_email: str,
        recipient_name: Optional[str],
        reset_url: str,
    ) -> bool:
        """Send a password reset link to a user."""
        if not self.is_configured:
            logger.warning(
                f"Cannot send password reset email to {recipient_email}: SMTP not configured"
            )
            return False

        return self.send_email(
            template=EmailTemplate.PASSWORD_RESET,
            recipient_email=recipient_email,
            subject="Reset your password - Rhesis AI",
            template_variables={
                "recipient_name": recipient_name or "",
                "reset_url": reset_url,
            },
            task_id="password_reset",
        )

    def send_magic_link_email(
        self,
        recipient_email: str,
        recipient_name: Optional[str],
        magic_link_url: str,
        is_new_user: bool = False,
    ) -> bool:
        """Send a magic link email to a user.

        Args:
            recipient_email: The recipient's email address.
            recipient_name: The recipient's display name.
            magic_link_url: The magic link URL.
            is_new_user: Whether this is a newly created account.
        """
        if not self.is_configured:
            logger.warning(
                "Cannot send magic link email to %s: SMTP not configured",
                recipient_email,
            )
            return False

        subject = "Welcome to Rhesis AI" if is_new_user else "Sign in to Rhesis AI"

        return self.send_email(
            template=EmailTemplate.MAGIC_LINK,
            recipient_email=recipient_email,
            subject=subject,
            template_variables={
                "recipient_name": recipient_name or "",
                "magic_link_url": magic_link_url,
                "is_new_user": is_new_user,
            },
            task_id="magic_link",
        )

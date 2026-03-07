"""
SendGrid v3 API client for sending emails with dynamic templates.
"""

import os
from datetime import datetime, timedelta, timezone
from email.utils import parseaddr
from typing import Optional, Tuple

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Email, Mail, To

from rhesis.backend.logging.rhesis_logger import logger


class SendGridClient:
    """Client for SendGrid v3 API operations."""

    def __init__(self):
        self.api_key = os.getenv("SENDGRID_API_KEY")
        self.is_configured = bool(self.api_key)

        if not self.is_configured:
            logger.warning("SendGrid API key not configured. Dynamic template emails disabled.")

    @staticmethod
    def _parse_email_address(email_string: str) -> Tuple[str, Optional[str]]:
        """
        Parse RFC822 email format into email address and optional name.

        Uses Python's stdlib email.utils.parseaddr() for robust RFC822 parsing.

        Handles formats like:
        - "Name" <email@example.com>
        - Name <email@example.com>
        - email@example.com

        Args:
            email_string: Email string in various formats

        Returns:
            Tuple of (email_address, name or None)
        """
        name, email = parseaddr(email_string)
        return email, name if name else None

    def send_scheduled_dynamic_template(
        self,
        template_id: str,
        recipient_email: str,
        recipient_name: Optional[str],
        subject: str,
        from_email: str,
        dynamic_template_data: dict,
        delay_hours: int,
        delay_minutes: int = 0,
    ) -> bool:
        """
        Send an email using a SendGrid Dynamic Template with scheduling.

        Args:
            template_id: SendGrid Dynamic Template ID (e.g., 'd-abc123...')
            recipient_email: Email address of the recipient
            recipient_name: Name of the recipient (optional)
            subject: Email subject line
            from_email: Sender email address
            dynamic_template_data: Dictionary of template variables (Handlebars format)
            delay_hours: Hours to delay sending
            delay_minutes: Additional minutes to delay sending

        Returns:
            bool: True if email was sent successfully, False otherwise
        """
        if not self.is_configured:
            logger.warning(
                f"Cannot send scheduled email to {recipient_email}: SendGrid API key not configured"
            )
            return False

        try:
            send_at_time = datetime.now(timezone.utc) + timedelta(
                hours=delay_hours, minutes=delay_minutes
            )
            send_at_timestamp = int(send_at_time.timestamp())

            # Parse from_email to handle RFC822 format ("Name" <email>)
            from_email_addr, from_name = self._parse_email_address(from_email)
            from_email_obj = Email(from_email_addr, from_name)

            # Include recipient name if provided
            to_email_obj = (
                To(email=recipient_email, name=recipient_name)
                if recipient_name
                else recipient_email
            )

            message = Mail(
                from_email=from_email_obj,
                to_emails=to_email_obj,
                subject=subject,
            )

            message.template_id = template_id
            message.dynamic_template_data = dynamic_template_data
            message.send_at = send_at_timestamp

            sg = SendGridAPIClient(self.api_key)
            response = sg.send(message)

            logger.info(
                f"Scheduled email for {recipient_email} to be sent at "
                f"{send_at_time.isoformat()} (timestamp: {send_at_timestamp}). "
                f"SendGrid response: {response.status_code}"
            )

            return response.status_code in [200, 201, 202]

        except Exception:
            logger.exception(f"Failed to send scheduled email to {recipient_email}")
            return False

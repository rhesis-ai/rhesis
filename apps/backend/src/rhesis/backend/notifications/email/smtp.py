"""
SMTP service for sending emails via SendGrid or other SMTP providers.
"""

import os
import smtplib
import socket
from email.mime.multipart import MIMEMultipart

from rhesis.backend.logging.rhesis_logger import logger


class SMTPService:
    """Service for sending emails via SMTP (SendGrid)."""

    def __init__(self):
        self.smtp_host = os.getenv("SMTP_HOST")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_user = os.getenv("SMTP_USER")
        self.smtp_password = os.getenv("SMTP_PASSWORD")
        self.from_email = os.getenv("FROM_EMAIL", "engineering@rhesis.ai")

        # Check if all required SMTP configurations are present
        self.is_configured = all([self.smtp_host, self.smtp_user, self.smtp_password])

        if not self.is_configured:
            logger.warning("SMTP configuration incomplete. Email notifications will be disabled.")
            logger.warning(
                f"Missing SMTP config - HOST: {bool(self.smtp_host)}, USER: {bool(self.smtp_user)}, PASSWORD: {bool(self.smtp_password)}"
            )

    def send_message(
        self, msg: MIMEMultipart, recipient_email: str, task_id: str, bcc: str = None
    ) -> bool:
        """
        Send the email message with proper SSL/TLS handling and timeout.

        Args:
            msg: The email message to send
            recipient_email: Email address for logging
            task_id: Task ID for logging
            bcc: Optional BCC email address

        Returns:
            bool: True if email was sent successfully, False otherwise
        """
        if not self.is_configured:
            logger.warning(f"Cannot send email to {recipient_email}: SMTP not configured")
            return False

        logger.info(f"Connecting to SMTP server {self.smtp_host}:{self.smtp_port}")

        # Add BCC header if provided
        if bcc:
            msg["Bcc"] = bcc
            logger.info(f"Adding BCC recipient: {bcc}")

        # Set socket timeout to prevent hanging
        socket.setdefaulttimeout(30)

        try:
            # Choose connection method based on port
            if self.smtp_port == 465:
                # Port 465 requires SSL from the start
                with smtplib.SMTP_SSL(self.smtp_host, self.smtp_port, timeout=30) as server:
                    server.set_debuglevel(0)  # Set to 1 for debug output
                    server.login(self.smtp_user, self.smtp_password)
                    server.send_message(msg)
            else:
                # Port 587 (and others) use STARTTLS
                with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=30) as server:
                    server.set_debuglevel(0)  # Set to 1 for debug output
                    server.starttls()
                    server.login(self.smtp_user, self.smtp_password)
                    server.send_message(msg)

            logger.info(f"Email sent successfully to {recipient_email} for task {task_id}")
            return True

        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"SMTP Authentication failed: {str(e)}")
            logger.error("Please check your SMTP username and password")
            return False
        except smtplib.SMTPConnectError as e:
            logger.error(f"SMTP Connection failed: {str(e)}")
            logger.error(f"Could not connect to {self.smtp_host}:{self.smtp_port}")
            return False
        except smtplib.SMTPServerDisconnected as e:
            logger.error(f"SMTP Server disconnected: {str(e)}")
            return False
        except smtplib.SMTPDataError as e:
            error_code, error_message = e.args
            if error_code == 550 and b"does not match a verified Sender Identity" in error_message:
                logger.error(f"SendGrid Sender Identity Error: {str(e)}")
                logger.error(f"The from address '{self.from_email}' is not verified in SendGrid")
                logger.error("Please verify the sender identity in SendGrid Dashboard:")
                logger.error("1. Go to Settings → Sender Authentication")
                logger.error("2. Click 'Verify a Single Sender'")
                logger.error(f"3. Add and verify '{self.from_email}'")
                logger.error("4. Complete the email verification process")
            else:
                logger.error(f"SMTP Data Error: {str(e)}")
            return False
        except socket.timeout:
            logger.error("SMTP connection timed out after 30 seconds")
            logger.error(
                f"Check if {self.smtp_host}:{self.smtp_port} is accessible from your network"
            )
            return False
        except Exception as e:
            logger.error(f"Unexpected SMTP error: {str(e)}")
            logger.error(f"Error type: {type(e).__name__}")
            import traceback

            logger.error(f"Traceback: {traceback.format_exc()}")
            return False
        finally:
            # Reset socket timeout
            socket.setdefaulttimeout(None)

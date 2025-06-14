"""
Email notification service for task completion notifications.
"""

import os
import smtplib
import socket
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
from datetime import datetime
from pathlib import Path

from rhesis.backend.logging.rhesis_logger import logger
from rhesis.backend.templates.email_fragments import (
    TEXT_EXECUTION_TIME, TEXT_TEST_RUN_ID, TEXT_ERROR_DETAILS, TEXT_VIEW_RESULTS,
    HTML_EXECUTION_TIME_ROW, HTML_TEST_RUN_ID_ROW, HTML_ERROR_DETAILS_SECTION, HTML_VIEW_RESULTS_SECTION
)


class EmailService:
    """Service for sending email notifications via SMTP (SendGrid)."""
    
    def __init__(self):
        self.smtp_host = os.getenv("SMTP_HOST")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_user = os.getenv("SMTP_USER")
        self.smtp_password = os.getenv("SMTP_PASSWORD")
        self.from_email = os.getenv("FROM_EMAIL", "engineering@rhesis.ai")  # Default to engineering@rhesis.ai
        
        # Get template directory path
        self.template_dir = Path(__file__).parent.parent / "templates"
        
        # Log SMTP configuration (without passwords)
        logger.info(f"EmailService initialized with SMTP_HOST: {self.smtp_host}, SMTP_PORT: {self.smtp_port}, SMTP_USER: {self.smtp_user}, SMTP_PASSWORD: {'[SET]' if self.smtp_password else '[NOT SET]'}")
        logger.info(f"FROM_EMAIL: {self.from_email}")
        logger.info(f"Template directory: {self.template_dir}")
        
        # Check if all required SMTP configurations are present
        self.is_configured = all([
            self.smtp_host,
            self.smtp_user,
            self.smtp_password
        ])
        
        if not self.is_configured:
            logger.warning("SMTP configuration incomplete. Email notifications will be disabled.")
            logger.warning(f"Missing SMTP config - HOST: {bool(self.smtp_host)}, USER: {bool(self.smtp_user)}, PASSWORD: {bool(self.smtp_password)}")
        else:
            logger.info("SMTP configuration complete. Email notifications enabled.")
    
    def _load_template(self, template_name: str) -> str:
        """Load email template from file."""
        template_path = self.template_dir / template_name
        try:
            with open(template_path, 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            logger.error(f"Email template not found: {template_path}")
            raise
        except Exception as e:
            logger.error(f"Error loading email template {template_path}: {str(e)}")
            raise
    
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
        """
        Send a task completion email notification.
        
        Args:
            recipient_email: Email address to send to
            recipient_name: Name of the recipient
            task_name: Name of the task that completed
            task_id: Unique task identifier
            status: Task completion status (success/failed)
            execution_time: Time taken to execute the task
            error_message: Error message if task failed
            test_run_id: ID of the test run if applicable
            frontend_url: Base URL for the frontend to create links
            
        Returns:
            bool: True if email was sent successfully, False otherwise
        """
        if not self.is_configured:
            logger.warning(f"Cannot send email to {recipient_email}: SMTP not configured")
            return False
        
        logger.info(f"Starting email send process to {recipient_email} for task {task_id} with status {status}")
        
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f"Task Completed: {task_name} - {status.title()}"
            msg['From'] = self.from_email
            msg['To'] = recipient_email
            
            logger.debug(f"Created email message with subject: {msg['Subject']}")
            
            # Create email content
            text_content = self._create_text_content(
                recipient_name, task_name, task_id, status, 
                execution_time, error_message, test_run_id, frontend_url
            )
            html_content = self._create_html_content(
                recipient_name, task_name, task_id, status, 
                execution_time, error_message, test_run_id, frontend_url
            )
            
            logger.debug(f"Created email content - text length: {len(text_content)}, html length: {len(html_content)}")
            
            # Attach parts
            msg.attach(MIMEText(text_content, 'plain'))
            msg.attach(MIMEText(html_content, 'html'))
            
            # Send email with proper SSL/TLS handling
            return self._send_email_message(msg, recipient_email, task_id)
            
        except Exception as e:
            logger.error(f"Failed to send task completion email to {recipient_email}: {str(e)}")
            logger.error(f"Error type: {type(e).__name__}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return False
    
    def _send_email_message(self, msg: MIMEMultipart, recipient_email: str, task_id: str) -> bool:
        """
        Send the email message with proper SSL/TLS handling and timeout.
        
        Args:
            msg: The email message to send
            recipient_email: Email address for logging
            task_id: Task ID for logging
            
        Returns:
            bool: True if email was sent successfully, False otherwise
        """
        logger.info(f"Connecting to SMTP server {self.smtp_host}:{self.smtp_port}")
        
        # Set socket timeout to prevent hanging
        socket.setdefaulttimeout(30)
        
        try:
            # Choose connection method based on port
            if self.smtp_port == 465:
                # Port 465 requires SSL from the start
                logger.debug("Using SMTP_SSL for port 465")
                with smtplib.SMTP_SSL(self.smtp_host, self.smtp_port, timeout=30) as server:
                    server.set_debuglevel(0)  # Set to 1 for debug output
                    logger.debug("SSL connection established, logging in")
                    server.login(self.smtp_user, self.smtp_password)
                    logger.debug("SMTP login successful, sending message")
                    server.send_message(msg)
                    logger.debug("Message sent successfully")
            else:
                # Port 587 (and others) use STARTTLS
                logger.debug(f"Using SMTP with STARTTLS for port {self.smtp_port}")
                with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=30) as server:
                    server.set_debuglevel(0)  # Set to 1 for debug output
                    logger.debug("SMTP connection established, starting TLS")
                    server.starttls()
                    logger.debug("TLS started, logging in")
                    server.login(self.smtp_user, self.smtp_password)
                    logger.debug("SMTP login successful, sending message")
                    server.send_message(msg)
                    logger.debug("Message sent successfully")
            
            logger.info(f"Task completion email sent successfully to {recipient_email} for task {task_id}")
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
            if error_code == 550 and b'does not match a verified Sender Identity' in error_message:
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
            logger.error(f"Check if {self.smtp_host}:{self.smtp_port} is accessible from your network")
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
    
    def _create_text_content(
        self, 
        recipient_name: Optional[str],
        task_name: str,
        task_id: str,
        status: str,
        execution_time: Optional[str],
        error_message: Optional[str],
        test_run_id: Optional[str],
        frontend_url: Optional[str]
    ) -> str:
        """Create plain text email content from template."""
        
        template = self._load_template("email_task_completion.txt")
        
        greeting = f"Hello {recipient_name}," if recipient_name else "Hello,"
        
        # Build conditional content
        execution_time_text = TEXT_EXECUTION_TIME.format(execution_time=execution_time) if execution_time else ""
        test_run_id_text = TEXT_TEST_RUN_ID.format(test_run_id=test_run_id) if test_run_id else ""
        error_details_text = TEXT_ERROR_DETAILS.format(error_message=error_message) if (status.lower() == 'failed' and error_message) else ""
        view_results_text = TEXT_VIEW_RESULTS.format(frontend_url=frontend_url, test_run_id=test_run_id) if (frontend_url and test_run_id) else ""
        
        return template.format(
            greeting=greeting,
            status_upper=status.upper(),
            status_title=status.title(),
            task_name=task_name,
            task_id=task_id,
            completed_at=datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
            execution_time=execution_time_text,
            test_run_id=test_run_id_text,
            error_details=error_details_text,
            view_results_link=view_results_text
        )
    
    def _create_html_content(
        self, 
        recipient_name: Optional[str],
        task_name: str,
        task_id: str,
        status: str,
        execution_time: Optional[str],
        error_message: Optional[str],
        test_run_id: Optional[str],
        frontend_url: Optional[str]
    ) -> str:
        """Create HTML email content from template."""
        
        template = self._load_template("email_task_completion.html")
        
        greeting = f"Hello {recipient_name}," if recipient_name else "Hello,"
        status_color = "#28a745" if status.lower() == 'success' else "#dc3545"
        status_emoji = "✅" if status.lower() == 'success' else "❌"
        
        # Build conditional content
        execution_time_row = HTML_EXECUTION_TIME_ROW.format(execution_time=execution_time) if execution_time else ""
        test_run_id_row = HTML_TEST_RUN_ID_ROW.format(test_run_id=test_run_id) if test_run_id else ""
        error_details_section = HTML_ERROR_DETAILS_SECTION.format(error_message=error_message) if (status.lower() == 'failed' and error_message) else ""
        view_results_section = HTML_VIEW_RESULTS_SECTION.format(frontend_url=frontend_url, test_run_id=test_run_id) if (frontend_url and test_run_id) else ""
        
        return template.format(
            greeting=greeting,
            status_emoji=status_emoji,
            status_color=status_color,
            status_upper=status.upper(),
            status_title=status.title(),
            task_name=task_name,
            task_id=task_id,
            completed_at=datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
            execution_time_row=execution_time_row,
            test_run_id_row=test_run_id_row,
            error_details_section=error_details_section,
            view_results_section=view_results_section
        )

    def send_test_execution_summary_email(
        self,
        recipient_email: str,
        recipient_name: Optional[str],
        task_name: str,
        task_id: str,
        status: str,
        total_tests: int,
        tests_passed: int,
        tests_failed: int,
        execution_time: Optional[str] = None,
        test_run_id: Optional[str] = None,
        status_details: Optional[str] = None,
        frontend_url: Optional[str] = None
    ) -> bool:
        """
        Send a test execution summary email notification.
        
        Args:
            recipient_email: Email address to send to
            recipient_name: Name of the recipient
            task_name: Name of the test configuration
            task_id: Unique task identifier
            status: Execution status (success/failed/partial)
            total_tests: Total number of tests executed
            tests_passed: Number of tests that passed
            tests_failed: Number of tests that failed
            execution_time: Time taken to execute all tests
            test_run_id: ID of the test run if applicable
            status_details: Additional status information
            frontend_url: Base URL for the frontend to create links
            
        Returns:
            bool: True if email was sent successfully, False otherwise
        """
        if not self.is_configured:
            logger.warning(f"Cannot send test execution summary email to {recipient_email}: SMTP not configured")
            return False
        
        logger.info(f"Starting test execution summary email to {recipient_email} for task {task_id}")
        
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f"Test Execution Complete: {task_name} - {status.title()}"
            msg['From'] = self.from_email
            msg['To'] = recipient_email
            
            logger.debug(f"Created test execution summary email with subject: {msg['Subject']}")
            
            # Create email content using specialized templates
            text_content = self._create_test_summary_text_content(
                recipient_name, task_name, task_id, status, total_tests,
                tests_passed, tests_failed, execution_time, test_run_id, 
                status_details, frontend_url
            )
            html_content = self._create_test_summary_html_content(
                recipient_name, task_name, task_id, status, total_tests,
                tests_passed, tests_failed, execution_time, test_run_id, 
                status_details, frontend_url
            )
            
            logger.debug(f"Created test execution summary content - text length: {len(text_content)}, html length: {len(html_content)}")
            
            # Attach parts
            msg.attach(MIMEText(text_content, 'plain'))
            msg.attach(MIMEText(html_content, 'html'))
            
            # Send email with proper SSL/TLS handling
            return self._send_email_message(msg, recipient_email, task_id)
            
        except Exception as e:
            logger.error(f"Failed to send test execution summary email to {recipient_email}: {str(e)}")
            logger.error(f"Error type: {type(e).__name__}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return False
    
    def _create_test_summary_text_content(
        self, 
        recipient_name: Optional[str],
        task_name: str,
        task_id: str,
        status: str,
        total_tests: int,
        tests_passed: int,
        tests_failed: int,
        execution_time: Optional[str],
        test_run_id: Optional[str],
        status_details: Optional[str],
        frontend_url: Optional[str]
    ) -> str:
        """Create plain text email content for test execution summary."""
        
        template = self._load_template("email_test_execution_summary.txt")
        
        greeting = f"Hello {recipient_name}," if recipient_name else "Hello,"
        
        # Build test run link if available
        test_run_link = ""
        if frontend_url and test_run_id:
            test_run_link = f"\n\nView Results:\n{frontend_url}/test-runs/{test_run_id}"
        
        return template.format(
            greeting=greeting,
            status_upper=status.upper(),
            status_title=status.title(),
            task_name=task_name,
            total_tests=total_tests,
            tests_passed=tests_passed,
            tests_failed=tests_failed,
            execution_time=execution_time or "N/A",
            completed_at=datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
            test_run_link=test_run_link,
            status_details=status_details or ""
        )
    
    def _create_test_summary_html_content(
        self, 
        recipient_name: Optional[str],
        task_name: str,
        task_id: str,
        status: str,
        total_tests: int,
        tests_passed: int,
        tests_failed: int,
        execution_time: Optional[str],
        test_run_id: Optional[str],
        status_details: Optional[str],
        frontend_url: Optional[str]
    ) -> str:
        """Create HTML email content for test execution summary."""
        
        template = self._load_template("email_test_execution_summary.html")
        
        greeting = f"Hello {recipient_name}," if recipient_name else "Hello,"
        
        # Determine colors and styling based on status
        if status.lower() == "success":
            status_color = "#28a745"
            status_emoji = "✅"
            status_bg_color = "#d4edda"
            status_border_color = "#c3e6cb"
            status_text_color = "#155724"
        elif status.lower() == "partial":
            status_color = "#ffc107"
            status_emoji = "⚠️"
            status_bg_color = "#fff3cd"
            status_border_color = "#ffeaa7"
            status_text_color = "#856404"
        else:  # failed
            status_color = "#dc3545"
            status_emoji = "❌"
            status_bg_color = "#f8d7da"
            status_border_color = "#f5c6cb"
            status_text_color = "#721c24"
        
        # Build test run link section
        test_run_link_section = ""
        if frontend_url and test_run_id:
            test_run_link_section = f"""
    <div style="text-align: center; margin: 20px 0;">
        <a href="{frontend_url}/test-runs/{test_run_id}" 
           style="background: #007bff; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; display: inline-block; font-weight: bold;">
            View Detailed Results
        </a>
    </div>"""
        
        return template.format(
            greeting=greeting,
            status_emoji=status_emoji,
            status_color=status_color,
            status_upper=status.upper(),
            status_title=status.title(),
            task_name=task_name,
            total_tests=total_tests,
            tests_passed=tests_passed,
            tests_failed=tests_failed,
            execution_time=execution_time or "N/A",
            completed_at=datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
            status_bg_color=status_bg_color,
            status_border_color=status_border_color,
            status_text_color=status_text_color,
            status_details=status_details or "",
            test_run_link_section=test_run_link_section
        )


# Global email service instance
email_service = EmailService() 
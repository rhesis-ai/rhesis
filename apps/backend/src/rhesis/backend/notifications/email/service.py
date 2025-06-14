"""
Main email service that orchestrates SMTP and template services.
"""

import os
from email.mime.text import MIMEText
from typing import Any, Dict, Optional

from rhesis.backend.logging.rhesis_logger import logger
from .smtp import SMTPService
from .template_service import TemplateService, EmailTemplate


class EmailService:
    """Main email service for sending HTML notifications."""
    
    def __init__(self):
        self.smtp_service = SMTPService()
        self.template_service = TemplateService()
        
        logger.info("EmailService initialized with SMTP and Template services")
    
    @property
    def is_configured(self) -> bool:
        """Check if email service is properly configured."""
        return self.smtp_service.is_configured
    
    def send_email(
        self,
        template: EmailTemplate,
        recipient_email: str,
        subject: str,
        template_variables: Dict[str, Any],
        task_id: Optional[str] = None
    ) -> bool:
        """
        Send an email using the specified template.
        
        Args:
            template: The email template to use
            recipient_email: Email address to send to
            subject: Email subject line
            template_variables: Variables to pass to the template
            task_id: Optional task ID for logging purposes
            
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
            msg = MIMEText(html_content, 'html')
            msg['Subject'] = subject
            msg['From'] = self.smtp_service.from_email
            msg['To'] = recipient_email
            
            logger.debug(f"Created HTML email message with subject: {msg['Subject']}")
            logger.debug(f"HTML content length: {len(html_content)}")
            
            # Send email using SMTP service
            return self.smtp_service.send_message(msg, recipient_email, task_id or "generic")
            
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
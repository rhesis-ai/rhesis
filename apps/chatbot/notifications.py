"""
Email notification module for chatbot rate limit alerts.

Sends email notifications to hello@rhesis.ai when users exceed their rate limits.
"""

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from fastapi import Request


# SMTP Configuration
SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
FROM_EMAIL = os.getenv("FROM_EMAIL", "engineering@rhesis.ai")
ALERT_EMAIL = "hello@rhesis.ai"


def send_rate_limit_alert(
    request: Request,
    identifier: str,
    rate_limit_type: str,
    rate_limit_value: str
):
    """
    Send email notification when rate limit is exceeded.
    
    Args:
        request: FastAPI Request object
        identifier: Rate limit identifier (e.g., "authenticated:org:user" or "public:ip")
        rate_limit_type: "Authenticated" or "Public"
        rate_limit_value: Rate limit string (e.g., "1000/day")
    """
    # Only send if SMTP is configured
    if not all([SMTP_HOST, SMTP_USER, SMTP_PASSWORD]):
        print("⚠️ Rate limit exceeded but SMTP not configured - skipping email notification")
        return
    
    try:
        # Extract useful information from request
        user_agent = request.headers.get("User-Agent", "Unknown")
        org_id = request.headers.get("X-Organization-ID", "N/A")
        user_id = request.headers.get("X-User-ID", "N/A")
        endpoint = request.url.path
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        
        # Create email content
        subject = f"🚨 Chatbot Rate Limit Exceeded - {rate_limit_type}"
        
        body = f"""
Rate Limit Exceeded Alert
==========================

Timestamp: {timestamp}
Rate Limit Type: {rate_limit_type}
Rate Limit: {rate_limit_value}

Request Details:
- Endpoint: {endpoint}
- Identifier: {identifier}
- Organization ID: {org_id}
- User ID: {user_id}
- User Agent: {user_agent}

This alert indicates that a user has exceeded their daily chatbot quota.

Actions to Consider:
1. Review if this is legitimate high usage or potential abuse
2. Consider increasing rate limits for this user if needed
3. Contact the user if this is repeated behavior

Environment: {os.getenv('ENVIRONMENT', 'unknown')}
Chatbot Service
Rhesis AI
"""
        
        # Create message
        msg = MIMEMultipart()
        msg['From'] = FROM_EMAIL
        msg['To'] = ALERT_EMAIL
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        
        # Send email via SMTP
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as server:
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
        
        print(f"✅ Rate limit alert email sent to {ALERT_EMAIL} for {identifier}")
        
    except Exception as e:
        # Don't fail the request if email fails
        print(f"❌ Failed to send rate limit alert email: {e}")


def is_smtp_configured() -> bool:
    """
    Check if SMTP is properly configured.
    
    Returns:
        bool: True if all required SMTP settings are present
    """
    return all([SMTP_HOST, SMTP_USER, SMTP_PASSWORD])


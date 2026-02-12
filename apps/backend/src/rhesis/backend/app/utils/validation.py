"""
Validation utilities for the application.
"""

from email_validator import EmailNotValidError, validate_email


def validate_and_normalize_email(email: str, check_deliverability: bool = False) -> str:
    """
    Validate and normalize an email address.

    Args:
        email: The email address to validate and normalize
        check_deliverability: If True, verify the domain has valid MX records
            that can receive email. Use for user creation/invitations to catch
            typos and fake domains. Defaults to False for fast validation in
            login/lookup flows.

    Returns:
        str: The normalized email address

    Raises:
        ValueError: If the email is invalid or the domain cannot receive email
    """
    if not email or not email.strip():
        raise ValueError("Email address is required")

    try:
        validated_email = validate_email(email.strip(), check_deliverability=check_deliverability)
        return validated_email.normalized
    except EmailNotValidError as e:
        raise ValueError(f"Invalid email address: {str(e)}")


def is_valid_email(email: str) -> bool:
    """
    Check if an email address is valid without raising an exception.

    Args:
        email: The email address to check

    Returns:
        bool: True if valid, False otherwise
    """
    try:
        validate_and_normalize_email(email)
        return True
    except ValueError:
        return False

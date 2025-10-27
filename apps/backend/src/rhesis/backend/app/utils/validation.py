"""
Validation utilities for the application.
"""

from email_validator import EmailNotValidError, validate_email


def validate_and_normalize_email(email: str) -> str:
    """
    Validate and normalize an email address.

    Args:
        email: The email address to validate and normalize

    Returns:
        str: The normalized email address

    Raises:
        ValueError: If the email is invalid
    """
    if not email or not email.strip():
        raise ValueError("Email address is required")

    try:
        # Validate and normalize the email (check_deliverability=False for more lenient validation)
        validated_email = validate_email(email.strip(), check_deliverability=False)
        return validated_email.email
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

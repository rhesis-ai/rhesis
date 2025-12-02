import logging
import os
import re
import sys

from dotenv import load_dotenv

load_dotenv(override=True)


class SensitiveDataFilter(logging.Filter):
    """
    Logging filter to redact sensitive data from logs.

    Redacts:
    - Authorization headers (Bearer tokens, API keys, Basic auth)
    - API keys in various formats (X-API-Key, RHESIS_API_KEY, etc.)
    - Passwords and credentials
    - Session tokens and cookies
    - JWT tokens
    - Database connection strings
    - OAuth tokens and secrets
    - Private keys
    - Cloud provider credentials (AWS, GCP)
    """

    # Patterns to match and redact
    PATTERNS = [
        # Authorization header: "authorization: Bearer <token>"
        (
            re.compile(r"(authorization:\s*Bearer\s+)[\w\-\.]+", re.IGNORECASE),
            r"\1[REDACTED]",
        ),
        # Authorization header: "authorization: Basic <base64>"
        (
            re.compile(r"(authorization:\s*Basic\s+)[\w\+/=]+", re.IGNORECASE),
            r"\1[REDACTED]",
        ),
        # Authorization header without type: "authorization: <token>"
        (re.compile(r"(authorization:\s*)[\w\-\.]+", re.IGNORECASE), r"\1[REDACTED]"),
        # Cookie header: "cookie: session=<value>"
        (
            re.compile(r"(cookie:\s*[^;=]+=[^;,\s]+)", re.IGNORECASE),
            r"cookie: [REDACTED]",
        ),
        # Set-Cookie header
        (
            re.compile(r"(set-cookie:\s*[^;=]+=[^;,\s]+)", re.IGNORECASE),
            r"set-cookie: [REDACTED]",
        ),
        # Custom auth headers (X-API-Key, X-Auth-Token, etc.)
        (
            re.compile(r"(x-[a-z\-]*(?:api|auth|token)[a-z\-]*:\s*)[\w\-\.]+", re.IGNORECASE),
            r"\1[REDACTED]",
        ),
        # API key patterns in various formats
        (
            re.compile(r"(api[-_]?key[\"']?\s*[:=]\s*[\"']?)[\w\-]+", re.IGNORECASE),
            r"\1[REDACTED]",
        ),
        # RHESIS API keys specifically (rh-*)
        (
            re.compile(r"(rh-[\w]{40,})", re.IGNORECASE),
            r"rh-[REDACTED]",
        ),
        # Password patterns
        (
            re.compile(r"(password[\"']?\s*[:=]\s*[\"']?)[^\s\"']+", re.IGNORECASE),
            r"\1[REDACTED]",
        ),
        # Secret patterns
        (
            re.compile(r"(secret[\"']?\s*[:=]\s*[\"']?)[\w\-\.]+", re.IGNORECASE),
            r"\1[REDACTED]",
        ),
        # Session token patterns
        (
            re.compile(r"(session[-_]?token[\"']?\s*[:=]\s*[\"']?)[\w\-\.]+", re.IGNORECASE),
            r"\1[REDACTED]",
        ),
        # JWT tokens (eyJ... pattern)
        (
            re.compile(r"\beyJ[\w\-\.]+\.eyJ[\w\-\.]+\.[\w\-\.]+", re.IGNORECASE),
            r"[REDACTED_JWT]",
        ),
        # OAuth access/refresh tokens
        (
            re.compile(
                r"((?:access|refresh)[-_]?token[\"']?\s*[:=]\s*[\"']?)[\w\-\.]+", re.IGNORECASE
            ),
            r"\1[REDACTED]",
        ),
        # OAuth client secrets
        (
            re.compile(r"(client[-_]?secret[\"']?\s*[:=]\s*[\"']?)[\w\-]+", re.IGNORECASE),
            r"\1[REDACTED]",
        ),
        # Database connection strings with passwords
        (
            re.compile(
                r"((?:postgres|mysql|mongodb)://[^:]+:)([^@]+)(@)",
                re.IGNORECASE,
            ),
            r"\1[REDACTED]\3",
        ),
        # AWS access keys (AKIA...)
        (
            re.compile(r"(AKIA[\w]{16})", re.IGNORECASE),
            r"AKIA[REDACTED]",
        ),
        # AWS secret keys
        (
            re.compile(
                r"(aws[-_]?secret[-_]?(?:access[-_]?)?key[\"']?\s*[:=]\s*[\"']?)[\w\+/=]+",
                re.IGNORECASE,
            ),
            r"\1[REDACTED]",
        ),
        # GCP service account keys
        (
            re.compile(
                r"(private_key[\"']?\s*[:=]\s*[\"']?)-----BEGIN[^-]+-----[^-]+-----END[^-]+-----",
                re.IGNORECASE,
            ),
            r"\1[REDACTED_PRIVATE_KEY]",
        ),
        # Generic token patterns (20+ chars)
        (
            re.compile(r"(token[\"']?\s*[:=]\s*[\"']?)[\w\-\.]{20,}", re.IGNORECASE),
            r"\1[REDACTED]",
        ),
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        """
        Filter log record to redact sensitive information.

        Args:
            record: Log record to filter

        Returns:
            True to allow the record to be logged (always returns True after redacting)
        """
        if isinstance(record.msg, str):
            for pattern, replacement in self.PATTERNS:
                record.msg = pattern.sub(replacement, record.msg)

        # Also redact in args if present
        if record.args:
            if isinstance(record.args, dict):
                record.args = {k: self._redact_value(v) for k, v in record.args.items()}
            elif isinstance(record.args, tuple):
                record.args = tuple(self._redact_value(arg) for arg in record.args)

        return True

    def _redact_value(self, value):
        """Redact sensitive data from a single value."""
        if isinstance(value, str):
            for pattern, replacement in self.PATTERNS:
                value = pattern.sub(replacement, value)
        return value


# Create a named logger
logger = logging.getLogger("__rhesis__")
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

# Prevent propagation to parent loggers to avoid duplicate messages
logger.propagate = False

# Only configure handlers if they haven't been added yet (prevents duplicates)
if not logger.handlers:
    # Create a console handler (Cloud Run captures logs from stdout)
    console_handler = logging.StreamHandler(stream=sys.stdout)
    console_handler.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

    # Set the formatter for the console handler
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%m/%d/%Y %I:%M:%S%p",
    )
    console_handler.setFormatter(formatter)

    # Add the console handler to the logger
    logger.addHandler(console_handler)

    # Conditionally add file logging only for local development
    if os.environ.get("ENV", "production") != "production":
        # Determine the log file path
        log_file_path = os.environ.get("LOG_FILE_PATH", "logs/rhesis.log")

        # Ensure the directory exists
        from pathlib import Path

        Path(log_file_path).parent.mkdir(parents=True, exist_ok=True)

        # Create a file handler
        file_handler = logging.FileHandler(log_file_path)
        file_handler.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

        # Set the formatter for the file handler
        file_formatter = logging.Formatter(
            "%(asctime)s | %(name)s | %(levelname)s | %(message)s",
            datefmt="%m/%d/%Y %I:%M:%S%p",
        )
        file_handler.setFormatter(file_formatter)

        # Add the file handler to the logger
        logger.addHandler(file_handler)

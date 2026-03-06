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

    PATTERNS = [
        (
            re.compile(r"(authorization:\s*Bearer\s+)[\w\-\.]+", re.IGNORECASE),
            r"\1[REDACTED]",
        ),
        (
            re.compile(r"(authorization:\s*Basic\s+)[\w\+/=]+", re.IGNORECASE),
            r"\1[REDACTED]",
        ),
        (
            re.compile(r"(authorization:\s*)[\w\-\.]+", re.IGNORECASE),
            r"\1[REDACTED]",
        ),
        (
            re.compile(r"(cookie:\s*[^;=]+=[^;,\s]+)", re.IGNORECASE),
            r"cookie: [REDACTED]",
        ),
        (
            re.compile(r"(set-cookie:\s*[^;=]+=[^;,\s]+)", re.IGNORECASE),
            r"set-cookie: [REDACTED]",
        ),
        (
            re.compile(
                r"(x-[a-z\-]*(?:api|auth|token)[a-z\-]*:\s*)[\w\-\.]+",
                re.IGNORECASE,
            ),
            r"\1[REDACTED]",
        ),
        (
            re.compile(
                r"(api[-_]?key[\"']?\s*[:=]\s*[\"']?)[\w\-]+",
                re.IGNORECASE,
            ),
            r"\1[REDACTED]",
        ),
        (
            re.compile(r"(rh-[\w]{40,})", re.IGNORECASE),
            r"rh-[REDACTED]",
        ),
        (
            re.compile(
                r"(password[\"']?\s*[:=]\s*[\"']?)[^\s\"']+",
                re.IGNORECASE,
            ),
            r"\1[REDACTED]",
        ),
        (
            re.compile(
                r"(secret[\"']?\s*[:=]\s*[\"']?)[\w\-\.]+",
                re.IGNORECASE,
            ),
            r"\1[REDACTED]",
        ),
        (
            re.compile(
                r"(session[-_]?token[\"']?\s*[:=]\s*[\"']?)[\w\-\.]+",
                re.IGNORECASE,
            ),
            r"\1[REDACTED]",
        ),
        (
            re.compile(
                r"\beyJ[\w\-\.]+\.eyJ[\w\-\.]+\.[\w\-\.]+",
                re.IGNORECASE,
            ),
            r"[REDACTED_JWT]",
        ),
        (
            re.compile(
                r"((?:access|refresh)[-_]?token[\"']?\s*[:=]\s*[\"']?)"
                r"[\w\-\.]+",
                re.IGNORECASE,
            ),
            r"\1[REDACTED]",
        ),
        (
            re.compile(
                r"(client[-_]?secret[\"']?\s*[:=]\s*[\"']?)[\w\-]+",
                re.IGNORECASE,
            ),
            r"\1[REDACTED]",
        ),
        (
            re.compile(
                r"((?:postgres|mysql|mongodb)://[^:]+:)([^@]+)(@)",
                re.IGNORECASE,
            ),
            r"\1[REDACTED]\3",
        ),
        (
            re.compile(r"(AKIA[\w]{16})", re.IGNORECASE),
            r"AKIA[REDACTED]",
        ),
        (
            re.compile(
                r"(aws[-_]?secret[-_]?(?:access[-_]?)?key[\"']?"
                r"\s*[:=]\s*[\"']?)[\w\+/=]+",
                re.IGNORECASE,
            ),
            r"\1[REDACTED]",
        ),
        (
            re.compile(
                r"(private_key[\"']?\s*[:=]\s*[\"']?)"
                r"-----BEGIN[^-]+-----[^-]+-----END[^-]+-----",
                re.IGNORECASE,
            ),
            r"\1[REDACTED_PRIVATE_KEY]",
        ),
        (
            re.compile(
                r"(token[\"']?\s*[:=]\s*[\"']?)[\w\-\.]{20,}",
                re.IGNORECASE,
            ),
            r"\1[REDACTED]",
        ),
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            for pattern, replacement in self.PATTERNS:
                record.msg = pattern.sub(replacement, record.msg)

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


def set_logger():
    """Configure the root logger for the application.

    Sets up console output, optional file logging for local development,
    and applies the sensitive data filter to all relevant loggers.

    Must be called once during application startup (e.g. in main.py).
    """
    log_level = os.environ.get("LOG_LEVEL", "INFO")

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    if root_logger.handlers:
        return

    console_handler = logging.StreamHandler(stream=sys.stdout)
    console_handler.setLevel(log_level)
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%m/%d/%Y %I:%M:%S%p",
    )
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    if os.environ.get("ENV", "production") != "production":
        log_file_path = os.environ.get("LOG_FILE_PATH", "logs/rhesis.log")

        from pathlib import Path

        Path(log_file_path).parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(log_file_path)
        file_handler.setLevel(log_level)
        file_formatter = logging.Formatter(
            "%(asctime)s | %(name)s | %(levelname)s | %(message)s",
            datefmt="%m/%d/%Y %I:%M:%S%p",
        )
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)

    sensitive_filter = SensitiveDataFilter()
    root_logger.addFilter(sensitive_filter)

    for name in ("uvicorn", "uvicorn.access", "websockets", "fastapi"):
        logging.getLogger(name).addFilter(sensitive_filter)

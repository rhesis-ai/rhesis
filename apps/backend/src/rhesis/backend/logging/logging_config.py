import json
import logging
import os
import re
import sys
from datetime import datetime
from pathlib import Path

from rhesis.backend.app.config.settings import get_application_settings, get_logging_settings

application_settings = get_application_settings()
logging_settings = get_logging_settings()

LOG_LEVEL = logging_settings.log_level
LOG_DIR = logging_settings.log_dir
ENVIRONMENT = application_settings.backend_env
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_DATE_FORMAT = "%m/%d/%Y %I:%M:%S%p"


_SENSITIVE_PATTERNS = [
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


def _redact(text: str) -> str:
    """Apply all sensitive-data patterns to *text* and return the redacted result."""
    for pattern, replacement in _SENSITIVE_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


class RedactingFormatter(logging.Formatter):
    """Formatter wrapper that redacts sensitive data from the final log output.

    Wraps an inner formatter and applies redaction patterns to the fully
    formatted string, avoiding in-place mutation of the shared LogRecord.
    This also catches values produced via extra fields and %-formatting args.
    """

    def __init__(self, inner: logging.Formatter):
        self._inner = inner

    def format(self, record: logging.LogRecord) -> str:
        return _redact(self._inner.format(record))

    def formatTime(self, record: logging.LogRecord, datefmt=None) -> str:
        return self._inner.formatTime(record, datefmt)

    def formatException(self, ei) -> str:
        return self._inner.formatException(ei)

    def formatStack(self, stack_info) -> str:
        return self._inner.formatStack(stack_info)


class JsonLogFormatter(logging.Formatter):
    """Format log records as Google Cloud-compatible structured JSON."""

    def format(self, record: logging.LogRecord) -> str:
        return json.dumps(
            {
                "severity": record.levelname,
                "module": record.name,
                "message": f"{record.name}: {record.getMessage()}",
            }
        )


class ColorFormatter(logging.Formatter):
    """Formatter that adds ANSI color codes to log level names for terminal output."""

    COLORS = {
        logging.DEBUG: "\033[36m",  # cyan
        logging.INFO: "\033[32m",  # green
        logging.WARNING: "\033[33m",  # yellow
        logging.ERROR: "\033[31m",  # red
        logging.CRITICAL: "\033[1;31m",  # bold red
    }
    RESET = "\033[0m"

    def format(self, record):
        color = self.COLORS.get(record.levelno, "")
        original = record.levelname
        record.levelname = f"{color}{record.levelname}{self.RESET}"
        result = super().format(record)
        record.levelname = original
        return result


def _create_formatter():
    return logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT)


def _create_color_formatter():
    return ColorFormatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT)


_configured = False


def set_logger():
    """Configure the root logger for the application.

    Sets up JSON console output with extra local-development output.
    All handlers use RedactingFormatter to ensure sensitive data is scrubbed
    from the final output without mutating shared LogRecord objects.

    Must be called once during application startup (e.g. in main.py).
    Subsequent calls are no-ops to prevent duplicate handlers.
    """
    global _configured
    if _configured:
        return
    _configured = True

    root_logger = logging.getLogger()
    root_logger.setLevel(LOG_LEVEL)

    # Remove any handlers added during module imports (e.g. Python's
    # default lastResort handler) so we control all output.
    root_logger.handlers.clear()

    if ENVIRONMENT == "local":
        color_console_handler = logging.StreamHandler(stream=sys.stdout)
        color_console_handler.setLevel(LOG_LEVEL)
        color_console_handler.setFormatter(RedactingFormatter(_create_color_formatter()))
        root_logger.addHandler(color_console_handler)

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        Path(LOG_DIR).mkdir(parents=True, exist_ok=True)

        log_file_path = os.path.join(LOG_DIR, f"rhesis_{timestamp}.log")
        file_handler = logging.FileHandler(log_file_path)
        file_handler.setLevel(LOG_LEVEL)
        file_handler.setFormatter(RedactingFormatter(_create_formatter()))
        root_logger.addHandler(file_handler)
    else:
        # Any non-local environment (GKE dev/staging/production, Cloud Run, etc.)
        # gets structured JSON on stdout so container log collection always
        # captures request/error output, regardless of which cloud runs it.
        json_console_handler = logging.StreamHandler(stream=sys.stdout)
        json_console_handler.setLevel(LOG_LEVEL)
        json_console_handler.setFormatter(RedactingFormatter(JsonLogFormatter()))
        root_logger.addHandler(json_console_handler)

    for name in ("uvicorn", "uvicorn.access", "uvicorn.error", "websockets", "fastapi"):
        logger = logging.getLogger(name)
        logger.handlers.clear()
        logger.propagate = True

    # Suppress verbose Celery-internal loggers that emit misleading task-signature
    # dumps and other low-signal debug chatter at the DEBUG level.
    for name in (
        "celery.utils.functional",
        "celery.app.trace",
        "kombu.pidbox",
    ):
        logging.getLogger(name).setLevel(logging.WARNING)

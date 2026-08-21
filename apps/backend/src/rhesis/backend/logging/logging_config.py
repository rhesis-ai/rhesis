import json
import logging
import os
import re
import sys
from datetime import datetime
from pathlib import Path

from rhesis.backend.app.config.settings import get_application_settings, get_logging_settings
from rhesis.backend.app.utils.request_context import get_request_id

application_settings = get_application_settings()
logging_settings = get_logging_settings()

LOG_LEVEL = logging_settings.log_level
LOG_DIR = logging_settings.log_dir
ENVIRONMENT = application_settings.backend_env
JSON_LOGGER_ENABLED = application_settings.json_logger_enabled
DEV_MODE = application_settings.dev_mode
# role_prefix is "" for API; Celery workers get "[MAIN] - " via the filter.
LOG_FORMAT = "%(asctime)s - %(role_prefix)s%(request_prefix)s%(name)s - %(levelname)s - %(message)s"
LOG_DATE_FORMAT = "%m/%d/%Y %I:%M:%S%p"


#: Value characters. Stops where a value ends in prose, JSON or a dict repr;
#: excluding brackets and backslashes also stops an inserted ``[REDACTED]`` from
#: being matched again by a later pattern.
_VALUE = r"[^\s\"',;)}\[\]\\]+"

#: Optional quote around the separator, so a logged header dict repr still
#: matches: ``{'Authorization': 'Bearer ...'}``.
_SEP = r"[\"']?\s*[:=]\s*[\"']?\s*"

#: A few words may sit between the keyword and the separator. OpenAI's and
#: Anthropic's auth-error bodies read "Incorrect API key provided: sk-...", and
#: those bodies reach our logs verbatim through the endpoint invoker.
_FILLER = r"(?:\s+\w+){0,3}?"

#: Words that follow a secret keyword in ordinary diagnostics. Redacting these
#: hides the very thing the line was written to say.
_NON_SECRET_VALUES = frozenset(
    {
        "blank",
        "configured",
        "empty",
        "expired",
        "false",
        "found",
        "invalid",
        "missing",
        "nil",
        "no",
        "none",
        "not",
        "null",
        "present",
        "provided",
        "redacted",
        "required",
        "set",
        "true",
        "unknown",
        "unset",
    }
)


def _looks_like_secret(value: str) -> bool:
    """Whether a keyword's captured value is credential-shaped rather than prose."""
    parts = [part for part in re.split(r"[-_]", value) if part]
    if parts and all(part.lower() in _NON_SECRET_VALUES for part in parts):
        return False
    # A plain lowercase word is prose; credentials carry digits, case or separators.
    if value.isalpha() and value.islower():
        return False
    return len(value) >= 12 or any(char.isdigit() for char in value)


def _redact_if_secret(match: re.Match) -> str:
    """Replacement for keyword patterns: group 1 is the prefix, group 2 the value."""
    if _looks_like_secret(match.group(2)):
        return f"{match.group(1)}[REDACTED]"
    return match.group(0)


_SENSITIVE_PATTERNS = [
    # Shape-based first: these need no keyword beside them, which is the only way
    # to catch a key quoted inside an upstream error body or a traceback frame.
    (
        re.compile(r"\beyJ[\w\-\.]+\.eyJ[\w\-\.]+\.[\w\-\.]+", re.IGNORECASE),
        r"[REDACTED_JWT]",
    ),
    (
        re.compile(r"\bsk-[A-Za-z0-9_\-]{16,}", re.IGNORECASE),
        r"[REDACTED]",
    ),
    (
        re.compile(r"\b(?:gh[pousr]_|github_pat_)[A-Za-z0-9_]{16,}", re.IGNORECASE),
        r"[REDACTED]",
    ),
    (
        re.compile(r"\bxox[abprs]-[A-Za-z0-9\-]{10,}", re.IGNORECASE),
        r"[REDACTED]",
    ),
    (
        re.compile(r"\bAIza[0-9A-Za-z_\-]{30,}", re.IGNORECASE),
        r"[REDACTED]",
    ),
    (
        re.compile(r"(rh-[\w]{40,})", re.IGNORECASE),
        r"rh-[REDACTED]",
    ),
    (
        re.compile(r"(AKIA[\w]{16})", re.IGNORECASE),
        r"AKIA[REDACTED]",
    ),
    # Any scheme's userinfo password. Enumerating schemes missed both of ours:
    # SQLAlchemy writes "postgresql+psycopg2://" and the Celery broker "redis://".
    (
        re.compile(r"\b([a-z][a-z0-9+.\-]*://[^:/\s@]*:)([^@\s/]+)(@)", re.IGNORECASE),
        r"\1[REDACTED]\3",
    ),
    # Header name touching its value: unambiguously a credential, no shape check.
    (
        re.compile(rf"(authorization{_SEP}Bearer\s+)[\w\-\.]+", re.IGNORECASE),
        r"\1[REDACTED]",
    ),
    (
        re.compile(rf"(authorization{_SEP}Basic\s+)[\w\+/=]+", re.IGNORECASE),
        r"\1[REDACTED]",
    ),
    # The lookahead stops this from re-redacting the "Bearer"/"Basic" left behind
    # by the two patterns above.
    (
        re.compile(
            rf"(authorization{_SEP})(?!Bearer\b|Basic\b)[\w\-\.]+",
            re.IGNORECASE,
        ),
        r"\1[REDACTED]",
    ),
    # A Bearer token with no header name in reach -- rest_invoker logs whole
    # header dicts, and nesting puts the token well away from any name.
    (
        re.compile(r"\b(Bearer\s+)(?!token\b|auth)[\w\-\.=+/]{8,}", re.IGNORECASE),
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
            rf"(x-[a-z\-]*(?:api|auth|token)[a-z\-]*{_SEP})[\w\-\.]+",
            re.IGNORECASE,
        ),
        r"\1[REDACTED]",
    ),
    # Keyword patterns. A space is a separator too, not just - and _: an upstream
    # service's own error body says "invalid api key: sk-live-..." in prose. The
    # value is only redacted when it looks like a credential, so a diagnostic
    # ("api key: not configured") still reads.
    (
        re.compile(rf"(api[-_ ]?key{_FILLER}{_SEP})({_VALUE})", re.IGNORECASE),
        _redact_if_secret,
    ),
    (
        re.compile(rf"(password{_FILLER}{_SEP})({_VALUE})", re.IGNORECASE),
        _redact_if_secret,
    ),
    (
        re.compile(rf"(client[-_ ]?secret{_FILLER}{_SEP})({_VALUE})", re.IGNORECASE),
        _redact_if_secret,
    ),
    (
        re.compile(
            rf"(aws[-_ ]?secret[-_ ]?(?:access[-_ ]?)?key{_FILLER}{_SEP})({_VALUE})",
            re.IGNORECASE,
        ),
        _redact_if_secret,
    ),
    (
        re.compile(rf"(secret{_FILLER}{_SEP})({_VALUE})", re.IGNORECASE),
        _redact_if_secret,
    ),
    (
        re.compile(
            rf"((?:session|access|refresh)[-_ ]?token{_FILLER}{_SEP})({_VALUE})",
            re.IGNORECASE,
        ),
        _redact_if_secret,
    ),
    (
        re.compile(
            rf"(private_key{_SEP})"
            r"-----BEGIN[^-]+-----[^-]+-----END[^-]+-----",
            re.IGNORECASE,
        ),
        r"\1[REDACTED_PRIVATE_KEY]",
    ),
    (
        re.compile(rf"(token{_FILLER}{_SEP})([\w\-\.]{{20,}})", re.IGNORECASE),
        _redact_if_secret,
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


#: ``extra=`` keys copied onto the JSON payload. An allowlist rather than
#: "everything not standard on LogRecord": log fields are a queryable
#: interface, and letting any caller's stray kwarg become a field makes it
#: one nobody can rely on. Add a key here when you want to query by it.
_STRUCTURED_EXTRA_FIELDS = (
    "worker_role",
    # Ties a client's error_id to the log line holding the traceback.
    "request_id",
    # rhesis.backend.app.utils.usage_tracking -- token usage that could not be
    # billed to an org, or came from a model with no provenance stamp. Alerting
    # on these needs them as fields, not as prose inside `message`.
    "usage_marker",
    "provider",
    "model",
    "total_tokens",
)


class JsonLogFormatter(logging.Formatter):
    """Format log records as Google Cloud-compatible structured JSON."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "severity": record.levelname,
            "module": record.name,
            "message": f"{record.name}: {record.getMessage()}",
        }
        # Without this a logger.exception() reaches GCP with no frames at all;
        # stack_trace is the key Error Reporting parses. Redaction still applies:
        # set_logger wraps this formatter in RedactingFormatter, which redacts the
        # serialised payload, traceback text included.
        if record.exc_info:
            payload["stack_trace"] = self.formatException(record.exc_info)
        if record.stack_info:
            payload["stack_info"] = self.formatStack(record.stack_info)
        for field in _STRUCTURED_EXTRA_FIELDS:
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        return json.dumps(payload)


class _WorkerContextFilter(logging.Filter):
    """Stamp ``worker_role`` / ``role_prefix`` / ``request_id`` on every record.

    All empty outside a request (API startup, Celery, scripts).
    """

    def __init__(self, worker_role: str | None = None):
        super().__init__()
        self.worker_role = worker_role

    def filter(self, record: logging.LogRecord) -> bool:
        record.worker_role = self.worker_role
        record.role_prefix = f"[{self.worker_role}] - " if self.worker_role else ""
        # unhandled_exception_handler runs outside RequestIDMiddleware, so it
        # passes request_id through extra= after the ContextVar was reset.
        request_id = getattr(record, "request_id", None) or get_request_id()
        record.request_id = request_id or None
        record.request_prefix = f"[{request_id}] " if request_id else ""
        return True


#: Infra paths whose *successful* access lines are pure noise. Kubelet hits
#: /health every 10-15s per pod (charts/rhesis/values-prd.yaml), which is the
#: only access traffic an idle pod produces. Failures still log -- a 503 from a
#: probe is the signal worth having. Same idea as EXCLUDED_PREFIXES in
#: telemetry/middleware.py, applied to access logs instead of spans.
_QUIET_ACCESS_PATHS = frozenset({"/health", "/healthz"})


class _QuietProbeAccessFilter(logging.Filter):
    """Drop 2xx/3xx ``uvicorn.access`` lines for infra probe paths.

    Filtering here rather than by log level: uvicorn writes every access line at
    INFO whatever the status (``h11_impl.RequestResponseCycle.send``), so no
    level keeps the errors and drops the probes. ``--no-access-log`` is no help
    either -- it clears the logger's handlers at Config init, and set_logger
    runs later and re-propagates, which turns access logging back on.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        # uvicorn logs '%s - "%s %s HTTP/%s" %d' with
        # (client_addr, method, path_with_query, http_version, status). Matching
        # on the args rather than the formatted message keeps this cheap, and
        # means a uvicorn format change degrades to "log everything".
        args = record.args
        if not isinstance(args, tuple) or len(args) != 5:
            return True
        path, status = args[2], args[4]
        if not isinstance(path, str) or not isinstance(status, int) or status >= 400:
            return True
        return path.split("?", 1)[0] not in _QUIET_ACCESS_PATHS


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


_configured = False


def set_logger(worker_role: str | None = None):
    """Configure the root logger once at startup.

    Console: JSON if ``JSON_LOGGER_ENABLED``, else color on a TTY, else plain text.
    When ``DEV_MODE=true``, also write a timestamped plain-text file under
    ``LOG_DIR``. Optional ``worker_role`` (e.g. MAIN/ARCHITECT from Celery's
    node name) is included in JSON and as a plain-text prefix.
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

    if JSON_LOGGER_ENABLED:
        formatter: logging.Formatter = RedactingFormatter(JsonLogFormatter())
    elif sys.stdout.isatty():
        formatter = RedactingFormatter(ColorFormatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT))
    else:
        formatter = RedactingFormatter(logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT))

    console_handler = logging.StreamHandler(stream=sys.stdout)
    console_handler.setLevel(LOG_LEVEL)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    if DEV_MODE:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        Path(LOG_DIR).mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(os.path.join(LOG_DIR, f"rhesis_{timestamp}.log"))
        file_handler.setLevel(LOG_LEVEL)
        file_handler.setFormatter(
            RedactingFormatter(logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT))
        )
        root_logger.addHandler(file_handler)

    context_filter = _WorkerContextFilter(worker_role)
    for handler in root_logger.handlers:
        handler.addFilter(context_filter)

    for name in (
        "uvicorn",
        "uvicorn.access",
        "uvicorn.error",
        "websockets",
        "fastapi",
        "celery",
        "celery.worker",
    ):
        logger = logging.getLogger(name)
        logger.handlers.clear()
        logger.propagate = True

    logging.getLogger("uvicorn.access").addFilter(_QuietProbeAccessFilter())

    # Suppress verbose Celery-internal loggers that emit misleading task-signature
    # dumps and other low-signal debug chatter at the DEBUG level.
    for name in (
        "celery.utils.functional",
        "celery.app.trace",
        "kombu.pidbox",
    ):
        logging.getLogger(name).setLevel(logging.WARNING)

    # pdfminer emits per-token DEBUG lines while parsing OWASP report PDFs; under
    # uvicorn --log-level debug that can fill hundreds of MB and stall the
    # categories endpoint / cache warm-up for minutes. Child loggers (psparser,
    # pdfinterp, ...) inherit this level since none of them set their own.
    logging.getLogger("pdfminer").setLevel(logging.WARNING)

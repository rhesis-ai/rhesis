"""
Auto-Configure Service for AI-powered endpoint mapping generation.

Uses an LLM to analyze user-provided reference material (curl commands,
code snippets, API docs) and generate request/response mappings for
Rhesis endpoints.  The LLM produces everything — mappings, headers,
and a concrete probe request body — in a single call.
"""

import ipaddress
import json
import logging
import re
import socket
from dataclasses import dataclass
from pathlib import Path
from typing import Type
from urllib.parse import urlparse

import httpx
import jinja2
from pydantic import BaseModel
from sqlalchemy.orm import Session

from rhesis.backend.app.schemas.endpoint import (
    AutoConfigureRequest,
    AutoConfigureResult,
)
from rhesis.backend.app.utils.user_model_utils import get_user_generation_model
from rhesis.sdk.models.factory import get_model

logger = logging.getLogger(__name__)

TEMPLATE_DIR = Path(__file__).parent.parent.parent / "templates"


@dataclass
class ProbeOutcome:
    """Outcome of a single probe attempt."""

    success: bool
    body: dict | None
    status_code: int | None
    error: str | None


class AutoConfigureService:
    """Service for AI-powered endpoint auto-configuration."""

    MAX_PROBE_ATTEMPTS = 3

    def __init__(self, db: Session, user):
        self.db = db
        self.user = user
        self.jinja_env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(str(TEMPLATE_DIR)),
            autoescape=jinja2.select_autoescape(),
            trim_blocks=True,
            lstrip_blocks=True,
        )
        model = get_user_generation_model(self.db, self.user)
        self.llm = get_model(provider=model) if isinstance(model, str) else model

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    async def auto_configure(self, request: AutoConfigureRequest) -> AutoConfigureResult:
        """Run the full auto-configure pipeline: analyse -> probe -> done."""

        # Step 1 — LLM analyses input and generates everything
        try:
            result = self._analyse(request)
        except Exception as e:
            logger.error("Failed to analyse input: %s", e, exc_info=True)
            return AutoConfigureResult(
                status="failed",
                error=f"Could not parse the input: {e}",
                reasoning=(
                    "The AI could not identify an API request structure in the provided text."
                ),
            )

        # Override with pre-filled values if provided
        if request.url:
            result.url = request.url
        if request.method:
            result.method = request.method

        # Step 2 — Probe endpoint with self-correction retries
        if request.probe and result.url:
            result = await self._probe_with_retries(result, request)

        return result

    # ------------------------------------------------------------------
    # LLM calls
    # ------------------------------------------------------------------

    def _call_llm(
        self,
        template_name: str,
        context: dict,
        schema: Type[BaseModel],
    ) -> BaseModel:
        """Render a Jinja2 prompt, call the LLM, return a validated model."""
        template = self.jinja_env.get_template(template_name)
        prompt = template.render(context)
        response = self.llm.generate(prompt, schema=schema)

        if isinstance(response, dict) and response.get("error"):
            raise RuntimeError(str(response["error"]))

        if isinstance(response, dict):
            return schema(**response)
        return response

    # ------------------------------------------------------------------
    # Secret redaction
    # ------------------------------------------------------------------

    # Env-var references like $API_KEY or ${SECRET} — these are safe placeholders.
    _ENV_VAR_RE = re.compile(r"\$\{?\w+\}?")

    # Patterns that match real API keys/tokens.  Each tuple is
    # (compiled regex, replacement string).  Order matters — more
    # specific patterns first so they aren't consumed by generic ones.
    _SECRET_PATTERNS: list[tuple[re.Pattern, str]] = [
        # OpenAI project keys  (sk-proj-...)
        (re.compile(r"sk-proj-[A-Za-z0-9_-]{20,}"), "sk-proj-REDACTED"),
        # OpenAI / Anthropic style keys  (sk-ant-..., sk-...)
        (re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}"), "sk-ant-REDACTED"),
        (re.compile(r"sk-[A-Za-z0-9_-]{20,}"), "sk-REDACTED"),
        # AWS access key IDs
        (re.compile(r"AKIA[0-9A-Z]{16}"), "AKIA_REDACTED"),
        # Google API keys  (AIza...)
        (re.compile(r"AIza[0-9A-Za-z_-]{35}"), "AIza_REDACTED"),
        # Bearer tokens in header values  (preserve the "Bearer " prefix)
        (
            re.compile(r"(Bearer\s+)[A-Za-z0-9._\-]{20,}"),
            r"\1REDACTED",
        ),
        # Generic header-value secrets: lines like
        #   "x-api-key: <long value>"  or  'Authorization': 'token abc...'
        (
            re.compile(
                r"(?i)"
                r"((?:api[_-]?key|token|secret|password|authorization)"
                r"[\"':\s]{1,5})"
                r"([A-Za-z0-9._\-]{20,})"
            ),
            r"\1REDACTED",
        ),
    ]

    @classmethod
    def _redact_secrets(cls, text: str) -> str:
        """Replace likely API keys/tokens with REDACTED placeholders.

        Environment variable references ($VAR, ${VAR}) are preserved
        because they are safe placeholders, not real secrets.
        """
        # Strategy: temporarily replace env-var references with
        # sentinels so the secret patterns don't match them, apply
        # redaction, then restore the env-var references.
        env_vars: list[str] = cls._ENV_VAR_RE.findall(text)
        sentinel = "\x00ENV"
        protected = cls._ENV_VAR_RE.sub(sentinel, text)

        for pattern, replacement in cls._SECRET_PATTERNS:
            protected = pattern.sub(replacement, protected)

        # Restore env-var references in order
        for var in env_vars:
            protected = protected.replace(sentinel, var, 1)

        return protected

    # ------------------------------------------------------------------

    def _analyse(self, request: AutoConfigureRequest) -> AutoConfigureResult:
        """Single LLM call: analyse input and generate mappings + probe body."""
        sanitized_input = self._redact_secrets(request.input_text)
        if sanitized_input != request.input_text:
            logger.info("Redacted potential secrets from auto-configure input")
        return self._call_llm(
            "auto_configure.jinja2",
            {
                "input_text": sanitized_input,
                "url": request.url,
                "method": request.method,
            },
            AutoConfigureResult,
        )

    def _validate_url(self, url: str) -> None:
        """Validate URL to prevent SSRF attacks on cloud metadata services.

        Allows localhost and private networks (for local development).
        Blocks link-local addresses (169.254.0.0/16) used by cloud metadata services.

        Raises:
            ValueError: If URL points to a blocked address range.
        """
        try:
            parsed = urlparse(url)
            hostname = parsed.hostname
            if not hostname:
                raise ValueError("URL must include a hostname")

            # Resolve hostname to IP
            try:
                ip_str = socket.gethostbyname(hostname)
                ip = ipaddress.ip_address(ip_str)
            except (socket.gaierror, ValueError) as e:
                # If we can't resolve, let it fail naturally during probe
                logger.warning("Could not resolve hostname %s: %s", hostname, e)
                return

            # Block link-local (cloud metadata services like 169.254.169.254)
            if ip in ipaddress.ip_network("169.254.0.0/16"):
                raise ValueError(
                    f"Access to link-local addresses (cloud metadata services) is not allowed: {ip}"
                )

            # Explicitly allow localhost and private networks
            # (for local development and on-premise deployments)

        except ValueError:
            raise

    def _correct(
        self,
        result: AutoConfigureResult,
        error_body: str,
        error_status_code: int | None,
    ) -> AutoConfigureResult:
        """Single LLM call: fix the result based on a probe error."""
        try:
            return self._call_llm(
                "auto_configure_correct.jinja2",
                {
                    "result": result,
                    "error_body": error_body,
                    "error_status_code": error_status_code,
                },
                AutoConfigureResult,
            )
        except RuntimeError:
            logger.warning("LLM correction failed, keeping original result")
            return result

    # ------------------------------------------------------------------
    # Probe
    # ------------------------------------------------------------------

    async def _probe_endpoint(
        self,
        url: str,
        method: str,
        headers: dict,
        body: dict,
        auth_token: str | None = None,
    ) -> ProbeOutcome:
        """Send a single test request to the endpoint."""
        # Validate URL for SSRF protection
        try:
            self._validate_url(url)
        except ValueError as e:
            return ProbeOutcome(False, None, None, str(e))

        probe_headers = {"Content-Type": "application/json", **headers}

        # Generic auth token substitution in all header values
        if auth_token:
            for key, value in probe_headers.items():
                if isinstance(value, str) and "{{ auth_token }}" in value:
                    probe_headers[key] = value.replace("{{ auth_token }}", auth_token)

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.request(
                    method=method.upper(),
                    url=url,
                    headers=probe_headers,
                    json=body,
                )
            try:
                resp_body = resp.json()
            except Exception:
                resp_body = {"raw": resp.text[:2000]}

            if resp.is_success:
                return ProbeOutcome(True, resp_body, resp.status_code, None)

            error_msg = f"HTTP {resp.status_code}: {json.dumps(resp_body)[:500]}"
            return ProbeOutcome(False, resp_body, resp.status_code, error_msg)

        except httpx.ConnectError as e:
            return ProbeOutcome(False, None, None, f"Connection error: {e}")
        except httpx.TimeoutException as e:
            return ProbeOutcome(False, None, None, f"Request timed out: {e}")
        except Exception as e:
            return ProbeOutcome(False, None, None, f"Request failed: {e}")

    async def _probe_with_retries(
        self,
        result: AutoConfigureResult,
        request: AutoConfigureRequest,
    ) -> AutoConfigureResult:
        """Probe the endpoint, self-correcting via LLM on failure."""
        for attempt in range(self.MAX_PROBE_ATTEMPTS):
            result.probe_attempts = attempt + 1

            probe = await self._probe_endpoint(
                url=result.url,
                method=result.method,
                headers=dict(result.request_headers or {}),
                body=result.probe_request or {},
                auth_token=request.auth_token,
            )
            result.probe_status_code = probe.status_code

            if probe.success:
                result.probe_response = probe.body
                result.probe_success = True
                result.probe_error = None
                logger.info("Probe succeeded on attempt %d", result.probe_attempts)
                return result

            result.probe_error = probe.error
            logger.warning(
                "Probe attempt %d failed: %s",
                result.probe_attempts,
                probe.error,
            )

            # Don't self-correct on auth failures or network errors
            if probe.status_code in (401, 403) or probe.status_code is None:
                break

            # Ask LLM to correct if we have more attempts
            if attempt < self.MAX_PROBE_ATTEMPTS - 1:
                error_str = json.dumps(probe.body) if probe.body else str(probe.error)
                corrected = self._correct(result, error_str, probe.status_code)
                # Preserve probe diagnostics on the corrected result
                corrected.probe_attempts = result.probe_attempts
                corrected.probe_error = result.probe_error
                corrected.probe_status_code = result.probe_status_code
                # Keep the original URL/method (user-provided takes priority)
                corrected.url = result.url
                corrected.method = result.method
                result = corrected

        # Probe failed — cap confidence
        result.probe_success = False
        result.confidence = min(result.confidence, 0.5)
        if result.status == "success":
            result.status = "partial"
        result.warnings.append("Mapping generated but could not be verified via endpoint probe.")
        return result

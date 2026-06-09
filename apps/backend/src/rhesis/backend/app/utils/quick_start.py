"""
Quick Start mode detection utility.

This module provides fail-secure detection for Quick Start mode.
Quick Start is ONLY enabled when QUICK_START=true AND all signals confirm local development.
"""

import logging
from typing import Optional

from rhesis.backend.app.config.settings import get_application_settings

logger = logging.getLogger(__name__)


def is_quick_start_enabled(hostname: Optional[str] = None, headers: Optional[dict] = None) -> bool:
    """
    Determine if Quick Start mode should be enabled.

    Quick Start is ONLY enabled when ALL of the following conditions are met:
    1. The process-level gate passes (QUICK_START is 'true' and no Google Cloud
       environment signals are present) -- see
       ``ApplicationSettings.quick_start_allowed_by_env``
    2. Hostname/domain does NOT match a known cloud-platform domain
    3. HTTP headers do NOT carry known cloud-platform fingerprints

    This is a fail-secure function: if ANY signal indicates cloud deployment,
    it returns False. Default is False for safety. Note that the security
    boundary is the explicit, opt-in env gate (step 1); the request-level
    checks are generic, non-branded cloud-platform fingerprints kept only as
    defense-in-depth.

    Args:
        hostname: Optional hostname to check (from request or manual override)
        headers: Optional HTTP headers dict to inspect

    Returns:
        bool: True ONLY if all signals confirm quick start mode, False otherwise

    Examples:
        >>> # Quick start enabled in local environment
        >>> is_quick_start_enabled()
        True

        >>> # Quick start disabled if a cloud-platform domain is present
        >>> is_quick_start_enabled(hostname="my-service.a.run.app")
        False
    """
    # 1. Process-level gate (QUICK_START + Google Cloud env signals).
    #    Deployment-static checks live on ApplicationSettings so they stay in
    #    one place alongside the rest of the environment detection.
    if not get_application_settings().quick_start_allowed_by_env:
        return False

    logger.debug("Quick Start environment variable set to 'true', validating deployment signals...")

    # 2. HOSTNAME/DOMAIN CHECKS - Fail if a cloud-platform domain is detected
    if hostname:
        hostname_lower = hostname.lower()

        # Google Cloud Run domains
        cloud_run_domains = [
            ".run.app",
            ".cloudrun.dev",
            ".appspot.com",
        ]

        # Check for Cloud Run domains
        for cloud_domain in cloud_run_domains:
            if cloud_domain in hostname_lower:
                logger.warning(f" Quick Start disabled: Cloud Run domain detected ({hostname})")
                return False

    # 3. HTTP HEADERS CHECKS - Fail if cloud headers detected
    if headers:
        # Check for Cloud Run specific headers (compared case-insensitively)
        cloud_run_headers = [
            "x-cloud-trace-context",
            "x-appengine-",
        ]

        for header_key in headers.keys():
            if any(header_key.lower().startswith(h) for h in cloud_run_headers):
                logger.warning(f" Quick Start disabled: Cloud Run header detected ({header_key})")
                return False

    # All checks passed - Quick Start is enabled
    logger.info(" Quick Start mode enabled - all signals confirm local development")
    return True

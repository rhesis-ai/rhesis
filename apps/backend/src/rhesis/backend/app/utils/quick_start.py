"""
Quick Start mode detection utility.

This module provides fail-secure detection for Quick Start mode.
Quick Start is ONLY enabled when QUICK_START=true AND all signals confirm local development.
"""

import os
from typing import Optional

from rhesis.backend.logging import logger


def is_quick_start_enabled(hostname: Optional[str] = None, headers: Optional[dict] = None) -> bool:
    """
    Determine if Quick Start mode should be enabled.

    Quick Start is ONLY enabled when ALL of the following conditions are met:
    1. QUICK_START environment variable is explicitly set to 'true'
    2. Hostname/domain does NOT indicate cloud deployment
    3. HTTP headers do NOT indicate cloud deployment
    4. Google Cloud environment variables are NOT present

    This is a fail-secure function: if ANY signal indicates cloud deployment,
    it returns False. Default is False for safety.

    Args:
        hostname: Optional hostname to check (from request or manual override)
        headers: Optional HTTP headers dict to inspect

    Returns:
        bool: True ONLY if all signals confirm quick start mode, False otherwise

    Examples:
        >>> # Quick start enabled in local environment
        >>> is_quick_start_enabled()
        True

        >>> # Quick start disabled if any cloud signal present
        >>> is_quick_start_enabled(hostname="api.rhesis.ai")
        False
    """
    # 1. Check QUICK_START environment variable (default: false for safety)
    quick_start_env = os.getenv("QUICK_START", "false").lower() == "true"

    if not quick_start_env:
        logger.debug("Quick Start disabled: QUICK_START not set to 'true'")
        return False

    logger.debug("Quick Start environment variable set to 'true', validating deployment signals...")

    # 2. HOSTNAME/DOMAIN CHECKS - Fail if cloud domain detected
    if hostname:
        hostname_lower = hostname.lower()

        # Specific Rhesis cloud domains
        rhesis_cloud_domains = [
            "app.rhesis.ai",
            "dev-app.rhesis.ai",
            "stg-app.rhesis.ai",
            "api.rhesis.ai",
            "dev-api.rhesis.ai",
            "stg-api.rhesis.ai",
            "rhesis.ai",
            "rhesis.app",
        ]

        # Google Cloud Run domains
        cloud_run_domains = [
            ".run.app",
            ".cloudrun.dev",
            ".appspot.com",
        ]

        # Check for Rhesis cloud domains
        for cloud_domain in rhesis_cloud_domains:
            if cloud_domain in hostname_lower:
                logger.warning(f"⚠️  Quick Start disabled: Cloud hostname detected ({hostname})")
                return False

        # Check for Cloud Run domains
        for cloud_domain in cloud_run_domains:
            if cloud_domain in hostname_lower:
                logger.warning(f"⚠️  Quick Start disabled: Cloud Run domain detected ({hostname})")
                return False

    # 3. HTTP HEADERS CHECKS - Fail if cloud headers detected
    if headers:
        # Check for Rhesis cloud domains in Host header
        host = headers.get("host", headers.get("Host", "")).lower()
        if host:
            rhesis_cloud_domains = [
                "app.rhesis.ai",
                "dev-app.rhesis.ai",
                "stg-app.rhesis.ai",
                "api.rhesis.ai",
                "dev-api.rhesis.ai",
                "stg-api.rhesis.ai",
            ]

            for cloud_domain in rhesis_cloud_domains:
                if cloud_domain in host:
                    logger.warning(f"⚠️  Quick Start disabled: Cloud Host header detected ({host})")
                    return False

        # Check for X-Forwarded-Host (proxy/load balancer indicator)
        forwarded_host = headers.get("x-forwarded-host", headers.get("X-Forwarded-Host", ""))
        if forwarded_host:
            logger.warning(
                f"⚠️  Quick Start disabled: X-Forwarded-Host header present ({forwarded_host})"
            )
            return False

        # Check for Cloud Run specific headers
        cloud_run_headers = [
            "x-cloud-trace-context",
            "X-Cloud-Trace-Context",
            "x-appengine-",
            "X-Appengine-",
        ]

        for header_key in headers.keys():
            if any(header_key.lower().startswith(h.lower()) for h in cloud_run_headers):
                logger.warning(f"⚠️  Quick Start disabled: Cloud Run header detected ({header_key})")
                return False

    # 4. GOOGLE CLOUD ENVIRONMENT CHECKS - Fail if GCP env vars present
    k_service = os.getenv("K_SERVICE")
    k_revision = os.getenv("K_REVISION")
    gcp_project = os.getenv("GCP_PROJECT") or os.getenv("GOOGLE_CLOUD_PROJECT")

    if k_service:
        logger.warning(
            f"⚠️  Quick Start disabled: K_SERVICE environment variable present ({k_service})"
        )
        return False

    if k_revision:
        logger.warning(
            f"⚠️  Quick Start disabled: K_REVISION environment variable present ({k_revision})"
        )
        return False

    if gcp_project:
        logger.warning(
            f"⚠️  Quick Start disabled: GCP_PROJECT environment variable present ({gcp_project})"
        )
        return False

    # All checks passed - Quick Start is enabled
    logger.info("✅ Quick Start mode enabled - all signals confirm local development")
    return True

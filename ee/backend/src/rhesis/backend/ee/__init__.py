"""Rhesis Enterprise Edition backend package.

This package registers EE features with the core FeatureRegistry at
application startup. It is loaded conditionally — if the package is not
installed (i.e. the ``ee`` extra was not requested), the application
runs in Community mode without any of the code in this directory being
imported.

Entry point
-----------
:func:`bootstrap` is the single function called by core at startup
(via ``apps/backend/src/rhesis/backend/app/ee_bootstrap.py``).
It receives the FastAPI app instance and registers all EE features and
routers that the current license allows.

Dependency rule
---------------
EE code may freely import from ``rhesis.backend.*`` (core). Core code
must NEVER import from ``rhesis.backend.ee.*`` directly. The only
core-side coupling is the ``try/except ImportError`` in
``ee_bootstrap.py``. Violating this rule breaks the "delete ee/ to get
a pure MIT build" guarantee and is caught by the ``community-boundary``
CI job.
"""

from __future__ import annotations

import logging
from importlib.metadata import PackageNotFoundError, version
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import FastAPI

logger = logging.getLogger(__name__)

try:
    __version__ = version("rhesis-backend-ee")
except PackageNotFoundError:
    # Reachable only in unusual dev configurations where the package metadata
    # is missing. Better to surface "unknown" than silently lie about a stale
    # hard-coded version that drifts from pyproject.toml.
    __version__ = "0+unknown"


def bootstrap(app: "FastAPI") -> None:
    """Register EE features and routers with the FastAPI *app*.

    Called once at application startup by
    :func:`rhesis.backend.app.ee_bootstrap.bootstrap_ee`. Registers each
    EE feature with :class:`~rhesis.backend.app.features.FeatureRegistry`
    and mounts its router onto *app* using the same authenticated route
    class as core routers, so the path-based public/token route lists
    apply uniformly.
    """
    from rhesis.backend.app.features import Feature, FeatureName, FeatureRegistry
    from rhesis.backend.ee.sso.router import router as sso_router
    from rhesis.backend.ee.sso.runtime_check import sso_runtime_check

    FeatureRegistry.register(
        Feature(
            name=FeatureName.SSO,
            display_name="Single Sign-On",
            runtime_check=sso_runtime_check,
            description="Per-organization OIDC-based SSO.",
        )
    )

    # EE routers must use the same authenticated route class as core routers
    # so the public/token route lists apply uniformly. Without this, the SSO
    # admin endpoints would silently fall back to vanilla APIRoute and any
    # future EE route relying on path-based auth would break.
    sso_router.route_class = app.router.route_class
    app.include_router(sso_router)
    logger.info("EE bootstrap complete - registered features: [sso]")

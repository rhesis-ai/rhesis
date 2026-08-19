"""Bootstrap hook for the Rhesis Enterprise Edition backend package.

This module is the **only** core-side coupling to ``rhesis.backend.ee``. It
attempts to import the EE package's ``bootstrap`` function at startup and
calls it with the FastAPI app instance. If the package is not installed (i.e.
the ``ee`` extra was not requested), the import fails silently and the
application continues in Community mode.

Call site
---------
``bootstrap_ee(app)`` is called once from ``main.py``, after the license
provider has been installed and all core routers have been mounted.

Dependency rule (enforced by ``community-boundary`` CI job)
-----------------------------------------------------------
This file may import from ``rhesis.backend.ee`` **only inside the
try/except block** shown below. No other file in ``apps/backend/src/``
may import from ``rhesis.backend.ee.*``.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import FastAPI

logger = logging.getLogger(__name__)


def bootstrap_ee_providers() -> None:
    """Install the EE license and quota providers without the full app bootstrap.

    Called from the Celery worker init signal so workers resolve licensed
    quota limits instead of falling back to free-tier defaults. No-op when
    the EE package is not installed.
    """
    try:
        from rhesis.backend.ee import bootstrap_providers  # type: ignore[import-untyped]
    except ImportError:
        return

    bootstrap_providers()


def bootstrap_ee(app: "FastAPI") -> None:
    """Conditionally load and initialise the EE package.

    If ``rhesis-backend-ee`` is not installed this is a no-op. When it is
    installed, ``rhesis.backend.ee.bootstrap(app)`` registers all EE
    features with :class:`~rhesis.backend.app.features.FeatureRegistry` and
    mounts their routers onto *app*.
    """
    try:
        from rhesis.backend.ee import bootstrap  # type: ignore[import-untyped]
    except ImportError:
        logger.debug("EE package not installed - running in Community mode")
        return

    logger.info("EE package found - bootstrapping enterprise features")
    bootstrap(app)

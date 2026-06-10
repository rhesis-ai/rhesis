"""Extension point for DB-required startup operations.

EE features (or any future plugin) that need a live database session at
startup can register a hook here.  The lifespan handler in ``main.py``
calls :func:`run_startup_hooks` once the DB session is available.

Pattern
-------
Register in your EE bootstrap (before the lifespan fires):

.. code-block:: python

    from rhesis.backend.app.startup_hooks import register_startup_hook
    register_startup_hook(sync_rbac_catalog)

Core's lifespan calls :func:`run_startup_hooks` with a scoped session.
Each hook receives ``(db: Session)`` and should be idempotent.

Contract
--------
- Hooks must be **idempotent**: they run on every startup.
- Hooks must not commit / rollback the session (the lifespan manages the
  transaction).
- Exceptions in a hook are logged and re-raised so a broken startup does
  not silently swallow misconfiguration.
- Registration is idempotent: calling ``register_startup_hook`` with the
  same callable twice is safe.

Dependency rule (enforced by ``community-boundary`` CI job)
-----------------------------------------------------------
This module is MIT core.  EE registers hooks here from its bootstrap via
the ``ee_bootstrap.py`` gate — no direct EE import in core.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Callable, List

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

#: Signature for a startup hook.
StartupHook = Callable[["Session"], None]

_hooks: List[StartupHook] = []


def register_startup_hook(hook: StartupHook) -> None:
    """Register *hook* to be called at application startup with a DB session.

    Idempotent: re-registering the same callable is a no-op, so a bootstrap
    that runs multiple times in a test suite is safe.

    Args:
        hook: A callable ``(db: Session) -> None``.  Must be idempotent.
    """
    if hook not in _hooks:
        _hooks.append(hook)
        logger.debug("startup hook registered: %s", getattr(hook, "__qualname__", repr(hook)))


def run_startup_hooks(db: "Session") -> None:
    """Execute all registered startup hooks in registration order.

    Called once from the ``main.py`` lifespan after ``initialize_local_environment``.
    Each hook failure is logged and re-raised so the process refuses to start
    rather than silently skipping a required initialization step.

    Args:
        db: Active SQLAlchemy session (caller owns the transaction).
    """
    for hook in _hooks:
        name = getattr(hook, "__qualname__", repr(hook))
        try:
            logger.info("running startup hook: %s", name)
            hook(db)
            logger.info("startup hook completed: %s", name)
        except Exception:
            logger.exception("startup hook FAILED: %s — aborting startup", name)
            raise


def reset_startup_hooks() -> None:
    """Clear all registered hooks.  For tests only."""
    _hooks.clear()


__all__ = [
    "StartupHook",
    "register_startup_hook",
    "reset_startup_hooks",
    "run_startup_hooks",
]

"""Typed execution context for @endpoint functions.

``EndpointContext`` carries tenant identity and provides scoped DB access.
Functions that need platform context declare a parameter with this type;
the :class:`~rhesis.sdk.connector.executor.TestExecutor` injects it
automatically based on the type annotation.

External SDK users writing ``@endpoint`` functions are unaffected -- they
simply do not declare an ``EndpointContext`` parameter.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, ContextManager, Optional


@dataclass(frozen=True)
class EndpointContext:
    """Platform context injected into ``@endpoint`` functions.

    Attributes:
        organization_id: Tenant organization identifier.
        user_id: Authenticated user identifier.

    The optional ``_db_factory`` allows callers to supply a custom
    session factory.  When omitted, :meth:`get_db` falls back to the
    backend's ``get_db_with_tenant_variables``.
    """

    organization_id: str
    user_id: str
    project_id: str = ""
    _db_factory: Optional[Callable[..., ContextManager[Any]]] = field(
        default=None, repr=False, compare=False
    )

    def get_db(self) -> ContextManager[Any]:
        """Return a context-managed DB session scoped to this tenant.

        Usage::

            with ctx.get_db() as db:
                rows = db.query(Model).all()

        A ``_db_factory`` **must** be supplied at construction time.
        Platform-side code (Celery tasks, HTTP routes, and the internal
        SDK connector) always provides one.  Calling this method on a
        context created without a factory raises :exc:`RuntimeError`.

        External SDK users writing ``@endpoint`` functions that do not
        declare a ``ctx: EndpointContext`` parameter are unaffected.
        """
        if self._db_factory is not None:
            return self._db_factory(self.organization_id, self.user_id, self.project_id)

        # Try the backend module as a fallback so the internal connector
        # (which runs inside the backend process) works without needing to
        # wire the factory explicitly through the SDK's ConnectorManager.
        # An ImportError means we are running outside the backend -- raise
        # a clear, actionable message instead of a confusing AttributeError.
        try:
            from rhesis.backend.app.database import get_db_with_tenant_variables

            return get_db_with_tenant_variables(self.organization_id, self.user_id, self.project_id)
        except ImportError:
            raise RuntimeError(
                "EndpointContext.get_db() requires a _db_factory when called "
                "outside the Rhesis backend.  Supply _db_factory at construction "
                "time:\n\n"
                "    ctx = EndpointContext(\n"
                "        organization_id=org_id,\n"
                "        user_id=user_id,\n"
                "        _db_factory=my_session_factory,\n"
                "    )\n"
            ) from None

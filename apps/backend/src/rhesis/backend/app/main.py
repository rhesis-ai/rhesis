"""
Main module for the FastAPI application.

This module creates the FastAPI application and includes all the routers
defined in the `routers` module. It also creates the database tables
using the `Base` object from the `database` module.

"""

import logging
import os
import time
from contextlib import AsyncExitStack, asynccontextmanager

# Initialize OpenTelemetry FIRST, before any OpenTelemetry imports
from rhesis.backend.telemetry import initialize_telemetry

initialize_telemetry()

# ruff: noqa: E402 - Imports must come after telemetry initialization
from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.sessions import SessionMiddleware

from rhesis.backend import __version__
from rhesis.backend.app.auth.public_routes import PUBLIC_ROUTES
from rhesis.backend.app.auth.user_utils import (
    require_current_user,
    require_current_user_or_token,
    require_current_user_or_token_without_context,
)
from rhesis.backend.app.config.settings import get_auth_settings, get_frontend_settings
from rhesis.backend.app.database import Base, engine, get_db
from rhesis.backend.app.error_handlers import (
    create_validation_error_response,
    log_validation_error,
)
from rhesis.backend.app.routers import routers
from rhesis.backend.app.utils.database_exceptions import ItemDeletedException, ItemNotFoundException
from rhesis.backend.app.utils.git_utils import get_version_info
from rhesis.backend.local_init import initialize_local_environment
from rhesis.backend.logging import set_logger
from rhesis.backend.telemetry.middleware import TelemetryMiddleware

logger = logging.getLogger(__name__)

Base.metadata.create_all(bind=engine)

# PUBLIC_ROUTES lives in rhesis.backend.app.auth.public_routes so EE can
# extend it from its bootstrap (e.g. to register its own public callback
# paths) before `app.include_router` runs for the EE routers.


def _inject_route_dependency(route: APIRoute, dependency) -> None:
    """Insert *dependency* as the first dependency on an already-registered route.

    Shared by :func:`apply_auth_backstop` (authentication) and
    :func:`apply_authz_backstop` (authorization).  Both rewrite a route's
    resolved ``dependant`` *after* registration rather than at decoration time:
    ``include_router`` copies each route with its own ``route_class``, so
    ``FastAPI(route_class=...)`` does not propagate to copied routes.  Rewriting
    the dependant post-hoc is the reliable way to cover every route, including
    those added by EE.

    ``get_parameterless_sub_dependant`` is what FastAPI uses internally for
    ``dependencies=[...]`` entries; inserting at index 0 makes the backstop run
    before the handler's own dependencies.
    """
    from fastapi.dependencies.utils import get_parameterless_sub_dependant

    sub_dependant = get_parameterless_sub_dependant(depends=dependency, path=route.path_format)
    route.dependant.dependencies.insert(0, sub_dependant)
    route.dependencies.insert(0, dependency)


def apply_authz_backstop(app: FastAPI) -> None:
    """Inject a permission check on every non-exempt HTTP route.

    Mirrors :func:`apply_auth_backstop` exactly, but for *authorization* rather
    than authentication.  Called **after** :func:`apply_auth_backstop` and
    :func:`~rhesis.backend.app.auth.capabilities.register_capabilities` so all
    routes (core + EE) are registered and the capability map is warm.

    For each :class:`~fastapi.routing.APIRoute`:

    1. Skip routes in :data:`~rhesis.backend.app.auth.public_routes.PUBLIC_ROUTES`
       — no auth, so no authz either.
    2. Skip routes in
       :data:`~rhesis.backend.app.auth.public_routes.AUTHZ_EXEMPT_ROUTES`
       — authenticated but deliberately exempt (onboarding, bootstrap).
    3. Resolve the route's capability via
       :func:`~rhesis.backend.app.auth.capabilities.get_capability_for_route`.
       If ``None`` (unmapped or in the deriver skip-list), leave the route
       unchanged — the CI drift guard (:mod:`tests.backend.security.test_authz_coverage`)
       will flag these as failures.
    4. Inject one parameterless ``require_permission(capability)`` sub-dependant
       using the same mechanism as :func:`apply_auth_backstop`
       (``get_parameterless_sub_dependant`` + ``route.dependant.dependencies.insert``).
       Because FastAPI deduplicates dependency results per request, the extra
       ``require_current_user_or_token`` call inside ``require_permission``
       resolves only once even when the handler also declares it.

    WebSocket routes (``APIWebSocketRoute``) and mounts are skipped; they
    authenticate and authorise manually in their handlers.
    """
    from rhesis.backend.app.auth.capabilities import get_capability_for_route
    from rhesis.backend.app.auth.public_routes import AUTHZ_EXEMPT_ROUTES, PUBLIC_ROUTES
    from rhesis.backend.app.auth.rbac import require_permission

    for route in app.router.routes:
        if not isinstance(route, APIRoute):
            continue
        path: str = route.path
        if path in PUBLIC_ROUTES:
            continue
        methods: set[str] = route.methods or set()
        if any((m, path) in AUTHZ_EXEMPT_ROUTES for m in methods):
            continue
        cap = get_capability_for_route(route)
        if cap is None:
            # Unmapped route — the drift guard in test_authz_coverage.py will flag this.
            continue
        _inject_route_dependency(route, Depends(require_permission(cap)))


# Authentication dependencies the backstop recognizes as "already protected".
#
# A route that declares any of these — directly or transitively via a tenant
# dependency such as ``get_tenant_db_session`` (which itself depends on
# ``require_current_user_or_token``) — is already authenticated. The backstop
# must NOT inject ``require_current_user_or_token`` on top of these, because
# some routes intentionally use a *weaker* policy: onboarding routes
# (``POST /organizations/``, ``PUT /users/{id}``) use
# ``require_current_user_or_token_without_context`` so a brand-new user who has
# no organization yet can create one. Blindly stacking the org-requiring
# variant on top breaks onboarding with a 403 ("User is not associated with an
# organization").
_AUTH_DEPENDENCY_CALLS = frozenset(
    {
        require_current_user_or_token,
        require_current_user_or_token_without_context,
        require_current_user,
    }
)


def _dependant_has_auth(dependant, seen: set | None = None) -> bool:
    """Recursively check whether a route's dependant tree declares any auth dependency.

    Walks the sub-dependency graph so transitive auth (e.g. a route depending on
    ``get_tenant_db_session`` -> ``get_tenant_context`` -> ``require_current_user_or_token``)
    is detected, not just auth declared directly on the handler.
    """
    if seen is None:
        seen = set()
    for sub in dependant.dependencies:
        call = getattr(sub, "call", None)
        if call in _AUTH_DEPENDENCY_CALLS:
            return True
        if call is not None and id(call) not in seen:
            seen.add(id(call))
            if _dependant_has_auth(sub, seen):
                return True
    return False


def apply_auth_backstop(app: FastAPI) -> None:
    """Append a baseline auth dependency to routes that declare none.

    Defense-in-depth backstop: every HTTP route whose exact path is **not** in
    :data:`PUBLIC_ROUTES` and that does **not** already declare an
    authentication dependency gets ``require_current_user_or_token`` injected,
    guaranteeing that no route is ever accidentally exposed without
    authentication.

    Routes that already declare an auth dependency are left untouched so their
    own (possibly weaker) policy remains authoritative. This matters for
    onboarding: ``POST /organizations/`` and ``PUT /users/{id}`` use
    ``require_current_user_or_token_without_context`` so a brand-new user with
    no organization can create one. Stacking the org-requiring
    ``require_current_user_or_token`` on top of those would reject onboarding
    with a 403 even though the route is correctly authenticated.

    Post-hoc injection (see :func:`_inject_route_dependency`) is used rather than
    a custom ``route_class`` because ``include_router`` copies routes with their
    own class and ``FastAPI(route_class=...)`` does not propagate.

    WebSocket routes (``APIWebSocketRoute``) and mounts are skipped; they
    authenticate manually in their handlers.

    Must be called **after** all routers (core + EE) and app-level routes are
    registered.
    """
    backstop = Depends(require_current_user_or_token)
    for route in app.router.routes:
        if not isinstance(route, APIRoute):
            continue
        if route.path in PUBLIC_ROUTES:
            continue
        # Skip routes that already authenticate themselves (directly or via a
        # tenant dependency). Injecting on top would override an intentionally
        # weaker policy such as the context-free auth used during onboarding.
        if _dependant_has_auth(route.dependant):
            continue
        _inject_route_dependency(route, backstop)


def get_api_description():
    """Generate API description with version information."""
    version_info = get_version_info()

    description = "API for testing and evaluating AI models.\n\n## Version Information\n"

    # Add version details
    description += f"- **Version**: {version_info['version']}\n"
    if "branch" in version_info:
        description += f"- **Branch**: {version_info['branch']}\n"
    if "commit" in version_info:
        description += f"- **Commit**: {version_info['commit']}\n"

    description += """
## URL Encoding
When using curl, special characters in URLs need to be URL-encoded. For example:
- Encoded: `/tests/?%24filter=prompt_id%20eq%20'89905869-e8e9-4b2f-b362-3598cfe91968'`
- Unencoded: `/tests/?$filter=prompt_id eq '89905869-e8e9-4b2f-b362-3598cfe91968'`

The `$` character must be encoded as `%24` when using curl.
Web browsers handle this automatically.
"""

    return description


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for FastAPI application.

    Handles startup and shutdown events using the modern lifespan approach.
    Replaces the deprecated @app.on_event("startup") and @app.on_event("shutdown").
    """
    set_logger()

    # Apply fail-fast Celery broker settings for the web process.
    # Must happen before any Celery task is published from an HTTP handler.
    from rhesis.backend.celery.core import apply_web_context_overrides

    apply_web_context_overrides()

    # Set anyio threadpool size for async-to-thread offloading.
    # Default is 40; 100 is a reasonable production value for 2 vCPU + concurrency 80.
    try:
        from anyio import to_thread

        await to_thread.run_sync(lambda: None)  # warm the thread limiter

        limiter = to_thread.current_default_thread_limiter()
        limiter.total_tokens = int(os.getenv("ANYIO_THREADPOOL_SIZE", "100"))
    except Exception as _tp_err:
        logger.warning(f"Could not configure anyio thread limiter: {_tp_err}")

    # Startup: Initialize local environment + run any registered startup hooks.
    # Startup hooks are registered by EE bootstrap (e.g. sync_rbac_catalog) and
    # must be idempotent.  Failures abort startup so misconfiguration is loud.
    #
    # Both calls share a single get_db() transaction deliberately: if either
    # fails the whole block rolls back atomically, avoiding a half-initialised
    # DB state (e.g. local env seeded but RBAC catalog missing, or vice versa).
    #
    # This block must complete and commit before the lifespan yield below so
    # that the permission/role catalog is fully populated before the first
    # request is served.  Requests that arrive before the sync commits would
    # query an empty permission table and either 403 every caller or raise.
    from rhesis.backend.app.startup_hooks import run_startup_hooks

    with get_db() as db:
        initialize_local_environment(db)
        run_startup_hooks(db)

    # Pre-fetch exchange rate on startup (non-blocking async)
    from rhesis.backend.app.services.exchange_rate import get_usd_to_eur_rate_async

    try:
        rate = await get_usd_to_eur_rate_async()
        logger.info(f"💱 Exchange rate initialized: 1 USD = {rate:.4f} EUR")
    except Exception as e:
        logger.warning(f"Failed to initialize exchange rate on startup: {e}")

    # Initialize Redis for SDK RPC (optional, doesn't fail startup)
    from rhesis.backend.app.services.connector.manager import connection_manager
    from rhesis.backend.app.services.connector.redis_client import redis_manager

    await redis_manager.initialize()  # Logs warning if fails, doesn't raise

    # Only start RPC listener if Redis is available
    if redis_manager.is_available:
        connection_manager._track_background_task(connection_manager._listen_for_rpc_requests())
        logger.info(
            "🚀 SDK RPC SYSTEM INITIALIZED - Workers can now invoke SDK functions via Redis bridge"
        )
    else:
        logger.warning(
            "⚠️ Redis not available - SDK RPC from workers will not work. "
            "Workers will not be able to invoke SDK functions."
        )

    # Initialize conversation linking cache (Redis with in-memory fallback)
    from rhesis.backend.app.services.telemetry.conversation_linking import (
        initialize_cache as init_conv_cache,
    )
    from rhesis.backend.app.services.telemetry.trace_metrics_cache import (
        initialize_cache as init_metrics_cache,
    )

    init_conv_cache()
    init_metrics_cache()

    # Initialize permission cache (Redis DB 5, in-memory fallback — SP5)
    from rhesis.backend.app.services.permission_cache import (
        initialize_cache as init_permission_cache,
    )

    init_permission_cache()

    # Initialize WebSocket Redis subscriber (optional, doesn't fail startup)
    from rhesis.backend.app.services.websocket import start_redis_subscriber, ws_manager

    try:
        await start_redis_subscriber(ws_manager)
        logger.info("🔌 WebSocket Redis subscriber started")
    except Exception as e:
        logger.warning(f"Failed to start WebSocket Redis subscriber: {e}")

    # Initialize Garak probe cache (optional, doesn't fail startup)
    from rhesis.backend.app.services.garak.cache import GarakProbeCache

    await GarakProbeCache.initialize()

    # Pre-warm Garak probe cache in background (non-blocking)
    # This ensures the first user request doesn't have to wait for probe enumeration
    import asyncio

    async def warm_garak_cache():
        """Background task to pre-warm Garak probe cache."""
        try:
            from rhesis.backend.app.services.garak import GarakProbeService

            service = GarakProbeService()
            await service.warm_cache()
            # Logging is handled by enumerate_probe_modules_cached
        except Exception as e:
            logger.warning(f"Garak cache pre-warming failed (non-fatal): {e}")

    # Launch as background task - store reference to prevent GC before completion
    # (per Python asyncio docs, tasks without references may be garbage collected)
    garak_cache_task = asyncio.create_task(warm_garak_cache())

    # Add exception handler to log errors (task runs in background, errors would be silent)
    def _log_task_exception(t: asyncio.Task) -> None:
        try:
            t.result()
        except asyncio.CancelledError:
            pass  # Expected during shutdown
        except Exception as e:
            logger.error(f"Garak cache pre-warming task failed: {e}", exc_info=True)

    garak_cache_task.add_done_callback(_log_task_exception)

    # Start MCP session manager (Mount doesn't propagate lifespan).
    # StreamableHTTPSessionManager.run() can only be called once per
    # instance, so create a fresh one each time the lifespan starts
    # (matters for test suites that restart the app multiple times).
    #
    # Use ``AsyncExitStack`` (not manual ``__aenter__``/``__aexit__``)
    # so the MCP context manager is entered and exited within a single
    # ``async with`` frame. ``StreamableHTTPSessionManager.run()`` wraps
    # an ``anyio.create_task_group()`` whose cancel scope is bound to the
    # asyncio task that entered it. Splitting enter/exit across the
    # ``yield`` of ``@asynccontextmanager`` makes the cleanup run via
    # ``agen.athrow()`` from a different task on SIGINT, which trips
    # anyio's "exit cancel scope in a different task" check.
    async with AsyncExitStack() as stack:
        mcp_server_obj = getattr(app.state, "mcp_server", None)
        if mcp_server_obj is not None:
            from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
            from mcp.server.transport_security import TransportSecuritySettings

            fresh_sm = StreamableHTTPSessionManager(
                app=mcp_server_obj,
                stateless=True,
                security_settings=TransportSecuritySettings(
                    enable_dns_rebinding_protection=False,
                ),
            )
            app.state.mcp_session_manager = fresh_sm
            await stack.enter_async_context(fresh_sm.run())
            logger.info("MCP session manager started")

        try:
            yield  # Application is running
        finally:
            # Shutdown order: MCP first (via stack.aclose()), then Redis/Garak/WS.
            # MCP is drained before Redis so any in-flight MCP frames that write
            # to Redis complete cleanly.
            # ``AsyncExitStack`` is used (not manual __aenter__/__aexit__) so
            # the MCP cancel scope is exited from the same asyncio task that
            # entered it, avoiding anyio's "exit cancel scope in a different
            # task" check on SIGINT.
            await stack.aclose()

            # Shutdown: Clean up Redis connections
            if redis_manager.is_available:
                await redis_manager.close()

            # Close Garak cache Redis connection
            await GarakProbeCache.close()

            # Stop WebSocket Redis subscriber
            from rhesis.backend.app.services.websocket import stop_redis_subscriber

            await stop_redis_subscriber()


app = FastAPI(
    title="Rhesis Backend",
    description=get_api_description(),
    version=__version__,
    lifespan=lifespan,
)

# Register rate limiter for slowapi (used by auth and user routers)
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from rhesis.backend.app.utils.rate_limit import limiter

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# Global exception handler for soft-deleted items
@app.exception_handler(ItemDeletedException)
async def deleted_item_exception_handler(request: Request, exc: ItemDeletedException):
    """Handle requests for soft-deleted items with HTTP 410 Gone."""
    import re

    # Convert model name from "TestRun" to "Test Run" (add space before capitals)
    model_name_display = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", exc.model_name)
    model_name_lower = model_name_display.lower()

    # Build response with item name if available
    response_content = {
        "detail": f"{model_name_display} has been deleted",
        "model_name": exc.model_name,
        "model_name_display": model_name_display,
        "item_id": exc.item_id,
        "table_name": exc.table_name,
        "restore_url": f"/recycle/{exc.table_name}/{exc.item_id}/restore",
        "can_restore": True,
        "message": (
            f"This {model_name_lower} has been deleted. You can restore it from the recycle bin."
        ),
    }

    # Include item name if available
    if exc.item_name:
        response_content["item_name"] = exc.item_name

    return JSONResponse(status_code=410, content=response_content)


# Global exception handler for not found items
@app.exception_handler(ItemNotFoundException)
async def not_found_item_exception_handler(request: Request, exc: ItemNotFoundException):
    """Handle requests for items that don't exist with HTTP 404 Not Found."""
    import re

    # Convert model name from "TestRun" to "Test Run" (add space before capitals)
    model_name_display = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", exc.model_name)
    model_name_lower = model_name_display.lower()

    # Get list URL from table name
    list_url = f"/{exc.table_name.replace('_', '-')}"

    # Build response
    response_content = {
        "detail": f"{model_name_display} not found",
        "model_name": exc.model_name,
        "model_name_display": model_name_display,
        "item_id": exc.item_id,
        "table_name": exc.table_name,
        "list_url": list_url,
        "message": (
            f"The {model_name_lower} you're looking for doesn't exist "
            "or you don't have permission to access it."
        ),
    }

    return JSONResponse(status_code=404, content=response_content)


# Global exception handler for request validation errors (422)
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle FastAPI request validation errors with detailed logging."""
    # Log the detailed validation error for debugging
    logger.error(
        f"Request validation error on {request.method} {request.url}: {exc}", exc_info=True
    )

    # Log detailed validation errors
    log_validation_error(exc, request)

    # Return clean JSON response
    return create_validation_error_response(exc)


# Configure CORS
_frontend_settings = get_frontend_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_frontend_settings.cors_origins,
    allow_origin_regex=_frontend_settings.loopback_cors_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Total-Count", "X-Test-Header"],
)

# Get session secret securely without default fallback in production
session_secret = get_auth_settings().session_secret_key

from rhesis.backend.app.routers.auth import is_running_locally

if not session_secret:
    if is_running_locally():
        session_secret = "fallback-secret-for-development"
    else:
        raise ValueError("CRITICAL: SESSION_SECRET_KEY must be set in production environments")

# Add session middleware
# For OAuth state preservation, we need proper cookie configuration
app.add_middleware(
    SessionMiddleware,
    secret_key=session_secret,
    session_cookie="session",
    max_age=3600,  # 1 hour session lifetime
    same_site="lax",  # Required for OAuth flows
    https_only=not is_running_locally(),  # Enforce HTTPS outside local development
)


# Add HTTPS redirect middleware
class HTTPSRedirectMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if "X-Forwarded-Proto" in request.headers:
            request.scope["scheme"] = request.headers["X-Forwarded-Proto"]
        return await call_next(request)


app.add_middleware(HTTPSRedirectMiddleware)

# Add telemetry middleware
app.add_middleware(TelemetryMiddleware)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-XSS-Protection"] = "0"

        if request.scope.get("scheme") == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        return response


# Outermost middleware -- runs first on every response
app.add_middleware(SecurityHeadersMiddleware)


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()

        # Log request
        logger.info(f"Request started: {request.method} {request.url}")

        # Sanitize headers before logging to redact sensitive information
        from rhesis.backend.app.services.invokers.common.headers import HeaderManager

        sanitized_headers = HeaderManager.sanitize_headers(dict(request.headers))
        logger.debug(f"Request headers: {sanitized_headers}")

        try:
            response = await call_next(request)

            # Log response
            process_time = time.time() - start_time
            logger.info(
                f"Request completed: {request.method} {request.url} "
                f"- Status: {response.status_code} - Duration: {process_time:.3f}s"
            )

            return response
        except Exception as e:
            logger.error(
                f"Request failed: {request.method} {request.url} - Error: {str(e)}", exc_info=True
            )
            raise


# Add the middleware to the app
# app.add_middleware(LoggingMiddleware)


# Include routers. The baseline auth dependency is applied post-hoc by
# apply_auth_backstop(app) at the end of this module, once every router
# (core + EE) and app-level route has been registered.
for router in routers:
    app.include_router(router)

# Mount MCP server for agent tool access
from rhesis.backend.app.mcp_server import setup_mcp_server

setup_mcp_server(app)

# Bootstrap Enterprise Edition features (no-op when ee extra is not installed).
#
# This intentionally runs at module load time rather than inside the lifespan
# handler because `bootstrap_ee` calls `app.include_router(...)`. FastAPI
# generates the OpenAPI schema lazily on first request; registering routes
# inside lifespan (after schema generation could have already been triggered)
# produces subtle schema-caching issues in some environments. Keeping it here
# guarantees routes and their docs are visible from the very first request.
#
# The call is safe at import time because `ee_bootstrap.bootstrap_ee` wraps
# the EE import in `try/except ImportError`, so it is a no-op in Community
# mode or in any test environment where the `ee` extra is not installed.
from rhesis.backend.app.ee_bootstrap import bootstrap_ee

bootstrap_ee(app)


@app.get("/", include_in_schema=True)
async def root():
    """Welcome endpoint with API status"""
    version_info = get_version_info()

    response_data = {
        "name": "Rhesis API",
        "status": "operational",
        **version_info,  # This will include version and optionally branch/commit
        "docs_url": "/docs",
        "redoc_url": "/redoc",
        "auth": {
            "login": "/auth/login",
            "callback": "/auth/callback",
            "logout": "/auth/logout",
        },
        "home": "/home",
        "api_usage": {
            "filtering": {
                "note": "When using curl, special characters in URLs need to be URL-encoded. "
                "For example:",
                "example": {
                    "encoded": "/tests/?%24filter=prompt_id%20eq%20'89905869-e8e9-4b2f-b362-"
                    "3598cfe91968'",
                    "unencoded": "/tests/?$filter=prompt_id eq '89905869-e8e9-4b2f-b362-"
                    "3598cfe91968'",
                    "note": "The $ character must be encoded as %24 when using curl. "
                    "Web browsers handle this automatically.",
                },
            }
        },
    }

    return JSONResponse(response_data)


@app.get("/health")
async def health_check():
    """Liveness + lightweight dependency surfacing.

    The endpoint stays 200 even when a non-fatal dependency is
    degraded; orchestrators rely on this for liveness, not readiness.
    Per-dependency status appears in the body so dashboards and
    on-call can see which subsystem flapped without paging.

    The Redis replay store ("redis_replay_store") is surfaced because
    a Redis outage degrades:

    - magic link / password reset single-use enforcement (already in
      core); and
    - subject-token replay protection in /auth/token-exchange (EE).

    Both fall back to fail-open on outage, so the body field lets
    operators correlate replay-protection gaps with infra incidents.
    """
    try:
        from rhesis.backend.app.services.connector.redis_client import (
            redis_manager,
        )

        redis_status = "ok" if redis_manager.is_available else "degraded"
    except Exception:
        # Surfacing the fact that the probe itself failed is more
        # useful than swallowing the error -- it points at a config
        # problem (e.g. missing env var) rather than a Redis outage.
        redis_status = "unknown"

    return {
        "status": "ok",
        "redis_replay_store": redis_status,
    }


# Defense-in-depth: append the baseline auth dependency to every non-public
# route. Runs last so it covers core routers, EE routers, and the app-level
# routes (/, /health) defined above.
apply_auth_backstop(app)

# Derive and cache the capability catalog from the now-complete route table.
# Must run after apply_auth_backstop so EE routes are already registered.
from rhesis.backend.app.auth.capabilities import register_capabilities

register_capabilities(app)

# PEP backstop: inject require_permission(capability) on every non-exempt route.
# Must run after register_capabilities so the capability map is warm (though the
# backstop derives caps independently via get_capability_for_route, keeping both
# in sync with the same deriver is belt-and-suspenders).
apply_authz_backstop(app)

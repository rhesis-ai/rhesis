"""
Main module for the FastAPI application.

This module creates the FastAPI application and includes all the routers
defined in the `routers` module. It also creates the database tables
using the `Base` object from the `database` module.

"""

import logging
import os
import time
from contextlib import asynccontextmanager

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
from rhesis.backend.app.auth.user_utils import require_current_user, require_current_user_or_token
from rhesis.backend.app.database import Base, engine, get_db
from rhesis.backend.app.error_handlers import (
    create_validation_error_response,
    log_validation_error,
)
from rhesis.backend.app.routers import routers
from rhesis.backend.app.utils.database_exceptions import ItemDeletedException, ItemNotFoundException
from rhesis.backend.app.utils.git_utils import get_version_info
from rhesis.backend.local_init import initialize_local_environment
from rhesis.backend.logging import logger
from rhesis.backend.telemetry.middleware import TelemetryMiddleware

Base.metadata.create_all(bind=engine)

# Public routes don't need any authentication
public_routes = [
    "/",
    "/auth/login",
    "/auth/callback",
    "/auth/logout",
    "/home",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/services/mcp/auth/callback",  # OAuth callback from external providers
]

# Routes that accept both session and token auth
token_enabled_routes = [
    "/api/",
    "/tokens/",
    "/tasks/",
    "/test_sets/",
    "/topics/",
    "/prompts/",
    "/test_configurations/",
    "/test_results/",
    "/test_runs/",
    "/services/",
    "/organizations/",
    "/demographics/",
    "/dimensions/",
    "/tags/",
    "/users/",
    "/statuses/",
    "/risks/",
    "/projects/",
    "/tests/",
    "/test-contexts/",
    "/comments/",
    "/sources/",
    "/models/",
    "/connector/",
]


def is_websocket_route(route: APIRoute) -> bool:
    """
    Check if a route is a WebSocket endpoint.

    WebSocket routes need special handling because they cannot use
    FastAPI's dependency injection system in the same way as HTTP routes.
    They must accept the connection first, then handle authentication manually.

    Args:
        route: The APIRoute to check

    Returns:
        True if this is a WebSocket route, False otherwise
    """
    import inspect

    # Check if the route has a dependant with a callable
    if not hasattr(route, "dependant") or not route.dependant:
        return False

    if not hasattr(route.dependant, "call") or not route.dependant.call:
        return False

    # Get the function signature
    try:
        sig = inspect.signature(route.dependant.call)
        # WebSocket routes have a 'websocket' parameter of type WebSocket
        return "websocket" in sig.parameters
    except (ValueError, TypeError):
        return False


class AuthenticatedAPIRoute(APIRoute):
    def get_dependencies(self):
        # WebSocket routes handle authentication manually in the endpoint
        if is_websocket_route(self):
            return []

        if self.path in public_routes:
            # No auth required
            return []
        elif any(self.path.startswith(route) for route in token_enabled_routes):
            # Both session and token auth accepted
            return [Depends(require_current_user_or_token)]
        # Default to session-only auth
        return [Depends(require_current_user)]


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
    # Startup: Initialize local environment if enabled
    with get_db() as db:
        initialize_local_environment(db)

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

    yield  # Application is running

    # Shutdown: Clean up Redis connection
    if redis_manager.is_available:
        await redis_manager.close()


app = FastAPI(
    title="Rhesis Backend",
    description=get_api_description(),
    version=__version__,
    route_class=AuthenticatedAPIRoute,
    lifespan=lifespan,
)


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
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://frontend:3000",
        "https://app.rhesis.ai",
        "https://dev-app.rhesis.ai",
        "https://dev-api.rhesis.ai",
        "https://stg-app.rhesis.ai",
        "https://stg-api.rhesis.ai",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Total-Count", "X-Test-Header"],
)

# Add session middleware
# For OAuth state preservation, we need proper cookie configuration
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("AUTH0_SECRET_KEY"),
    session_cookie="session",
    max_age=3600,  # 1 hour session lifetime
    same_site="lax",  # Required for OAuth flows
    https_only=False,  # False for local development (http)
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


# Include routers with custom route class
for router in routers:
    router.route_class = AuthenticatedAPIRoute
    app.include_router(router)


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
    return {"status": "ok"}


# Configure additional FastAPI logging
fastapi_logger = logging.getLogger("fastapi")
fastapi_logger.setLevel(logging.DEBUG)

# Apply sensitive data filter to prevent logging of auth tokens and API keys
from rhesis.backend.logging.rhesis_logger import SensitiveDataFilter

sensitive_filter = SensitiveDataFilter()

# Apply to websockets logger (logs WebSocket headers including Authorization)
websockets_logger = logging.getLogger("websockets")
websockets_logger.addFilter(sensitive_filter)

# Apply to uvicorn logger (logs HTTP headers)
uvicorn_logger = logging.getLogger("uvicorn")
uvicorn_logger.addFilter(sensitive_filter)

# Apply to uvicorn.access logger
uvicorn_access_logger = logging.getLogger("uvicorn.access")
uvicorn_access_logger.addFilter(sensitive_filter)

# Apply to our own application logger
fastapi_logger.addFilter(sensitive_filter)

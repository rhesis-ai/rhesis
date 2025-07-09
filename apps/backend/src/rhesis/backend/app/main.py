"""
Main module for the FastAPI application.

This module creates the FastAPI application and includes all the routers
defined in the `routers` module. It also creates the database tables
using the `Base` object from the `database` module.

"""

import logging
import os
import time

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.sessions import SessionMiddleware

from rhesis.backend import __version__
from rhesis.backend.app.auth.user_utils import require_current_user, require_current_user_or_token
from rhesis.backend.app.database import Base, engine
from rhesis.backend.app.routers import routers
from rhesis.backend.logging import logger

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
]


class AuthenticatedAPIRoute(APIRoute):
    def get_dependencies(self):
        if self.path in public_routes:
            # No auth required
            return []
        elif any(self.path.startswith(route) for route in token_enabled_routes):
            # Both session and token auth accepted
            return [Depends(require_current_user_or_token)]
        # Default to session-only auth
        return [Depends(require_current_user)]


app = FastAPI(
    title="RhesisAPI",
    description="""
    API for testing and evaluating AI models.
    
    ## URL Encoding
    When using curl, special characters in URLs need to be URL-encoded. For example:
    - Encoded: `/tests/?%24filter=prompt_id%20eq%20'89905869-e8e9-4b2f-b362-3598cfe91968'`
    - Unencoded: `/tests/?$filter=prompt_id eq '89905869-e8e9-4b2f-b362-3598cfe91968'`
    
    The `$` character must be encoded as `%24` when using curl. 
    Web browsers handle this automatically.
    """,
    version=__version__,
    route_class=AuthenticatedAPIRoute,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://app.rhesis.ai", "https://dev-app.rhesis.ai", "https://dev-api.rhesis.ai"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Total-Count", "X-Test-Header"],
)

# Add session middleware
app.add_middleware(SessionMiddleware, secret_key=os.getenv("AUTH0_SECRET_KEY"))


# Add HTTPS redirect middleware
class HTTPSRedirectMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if "X-Forwarded-Proto" in request.headers:
            request.scope["scheme"] = request.headers["X-Forwarded-Proto"]
        return await call_next(request)


app.add_middleware(HTTPSRedirectMiddleware)


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()

        # Log request
        logger.info(f"Request started: {request.method} {request.url}")
        logger.debug(f"Request headers: {request.headers}")

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
    return JSONResponse(
        {
            "name": "Rhesis API",
            "status": "operational",
            "version": __version__,
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
    )


@app.get("/health")
async def health_check():
    return {"status": "ok"}


# Configure additional FastAPI logging
fastapi_logger = logging.getLogger("fastapi")
fastapi_logger.setLevel(logging.DEBUG)

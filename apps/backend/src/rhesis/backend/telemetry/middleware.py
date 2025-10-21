"""
Middleware for handling telemetry context in FastAPI.
"""

import time
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from rhesis.backend.logging.rhesis_logger import logger
from rhesis.backend.telemetry.instrumentation import (
    _telemetry_org_id,
    _telemetry_user_id,
    get_tracer,
    set_telemetry_enabled,
)


class TelemetryMiddleware(BaseHTTPMiddleware):
    """
    Middleware that:
    1. Checks user's telemetry preference
    2. Sets telemetry context for the request
    3. Tracks API endpoint usage
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and track telemetry if enabled"""

        # Start timing
        start_time = time.time()

        # Process the request first (this runs dependencies and sets request.state.user)
        response = await call_next(request)

        # NOW check if user has telemetry enabled (after dependencies have run)
        user = getattr(request.state, "user", None)

        if user and hasattr(user, "telemetry_enabled"):
            telemetry_enabled = user.telemetry_enabled or False
            user_id = getattr(user, "id", None)
            org_id = getattr(user, "organization_id", None)

            logger.debug(
                f"TelemetryMiddleware: user={user_id}, telemetry_enabled={telemetry_enabled}"
            )

            # Set telemetry context for any spans created during this request
            set_telemetry_enabled(
                enabled=telemetry_enabled,
                user_id=str(user_id) if user_id else None,
                org_id=str(org_id) if org_id else None,
            )

            # Track endpoint usage if telemetry is enabled
            if telemetry_enabled:
                await self._track_endpoint(request, response, start_time, user_id, org_id)

        return response

    async def _track_endpoint(
        self, request: Request, response: Response, start_time: float, user_id, org_id
    ):
        """Track API endpoint usage after request is completed"""
        try:
            tracer = get_tracer(__name__)

            # Get route info
            route = request.url.path
            method = request.method

            # Calculate duration
            duration_ms = (time.time() - start_time) * 1000

            with tracer.start_as_current_span(f"http.{method}.{route}") as span:
                # Set HTTP attributes
                span.set_attribute("event.category", "endpoint_usage")
                span.set_attribute("http.method", method)
                span.set_attribute("http.route", route)
                span.set_attribute("http.url", str(request.url))
                span.set_attribute("http.status_code", response.status_code)
                span.set_attribute("duration_ms", duration_ms)

                # Set user context (use hashed IDs from context)
                hashed_user_id = _telemetry_user_id.get()
                hashed_org_id = _telemetry_org_id.get()

                if hashed_user_id:
                    span.set_attribute("user.id", hashed_user_id)
                if hashed_org_id:
                    span.set_attribute("organization.id", hashed_org_id)

        except Exception as e:
            logger.error(f"Error tracking endpoint: {e}")

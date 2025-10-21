"""
Middleware for handling telemetry context in FastAPI.
"""

import time
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from rhesis.backend.logging.rhesis_logger import logger
from rhesis.backend.telemetry.instrumentation import (
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

        # Check if user has telemetry enabled
        user = getattr(request.state, "user", None)

        if user and hasattr(user, "telemetry_enabled"):
            telemetry_enabled = user.telemetry_enabled or False
            user_id = getattr(user, "id", None)
            org_id = getattr(user, "organization_id", None)

            # Set telemetry context
            set_telemetry_enabled(
                enabled=telemetry_enabled,
                user_id=str(user_id) if user_id else None,
                org_id=str(org_id) if org_id else None,
            )

            # Track endpoint usage if telemetry is enabled
            if telemetry_enabled:
                await self._track_request(request, call_next, start_time, user_id, org_id)
                return await call_next(request)

        # No telemetry tracking
        response = await call_next(request)
        return response

    async def _track_request(
        self, request: Request, call_next: Callable, start_time: float, user_id, org_id
    ):
        """Track API endpoint usage"""
        try:
            tracer = get_tracer(__name__)

            # Get route info
            route = request.url.path
            method = request.method

            with tracer.start_as_current_span(f"http.{method}.{route}") as span:
                # Set HTTP attributes
                span.set_attribute("event.category", "endpoint_usage")
                span.set_attribute("http.method", method)
                span.set_attribute("http.route", route)
                span.set_attribute("http.url", str(request.url))

                # Set user context
                if user_id:
                    span.set_attribute("user.id", str(user_id))
                if org_id:
                    span.set_attribute("organization.id", str(org_id))

                # Execute request
                response = await call_next(request)

                # Calculate duration
                duration_ms = (time.time() - start_time) * 1000

                # Set response attributes
                span.set_attribute("http.status_code", response.status_code)
                span.set_attribute("duration_ms", duration_ms)

                return response

        except Exception as e:
            logger.error(f"Error tracking request: {e}")
            return await call_next(request)

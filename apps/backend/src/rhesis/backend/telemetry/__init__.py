"""
OpenTelemetry instrumentation for Rhesis backend.

This module provides conditional telemetry export based on user preferences.
"""

from .instrumentation import (
    get_tracer,
    initialize_telemetry,
    set_telemetry_enabled,
    track_feature_usage,
    track_user_activity,
)

__all__ = [
    "initialize_telemetry",
    "get_tracer",
    "set_telemetry_enabled",
    "track_user_activity",
    "track_feature_usage",
]

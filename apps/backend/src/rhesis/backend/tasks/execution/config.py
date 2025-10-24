"""
Redis-based Celery configuration for task execution.

Environment variables:
- BROKER_URL: Redis broker URL (default: redis://localhost:6379/0)
- CELERY_RESULT_BACKEND: Redis result backend URL (default: redis://localhost:6379/1)
- REDIS_MAX_CONNECTIONS: Maximum Redis connections (default: 20)
"""

import os
from typing import Any, Dict
from uuid import UUID

from sqlalchemy.orm import Session

from rhesis.backend.app import crud
from rhesis.backend.app.models.test_configuration import TestConfiguration


class TestConfigurationError(Exception):
    """Exception raised for errors in test configuration."""

    pass


def get_test_configuration(
    session: Session, test_configuration_id: str, organization_id: str = None
) -> TestConfiguration:
    """Retrieve and validate test configuration."""
    # Use the crud utility directly
    test_config = crud.get_test_configuration(
        session, test_configuration_id=UUID(test_configuration_id), organization_id=organization_id
    )

    if not test_config:
        raise ValueError(f"Test configuration {test_configuration_id} not found")

    if not test_config.test_set_id:
        raise ValueError(f"Test configuration {test_configuration_id} has no test set assigned")

    return test_config


def get_redis_config() -> Dict[str, Any]:
    """Get Redis-optimized Celery configuration."""
    return {
        # Redis URLs
        "broker_url": os.getenv("BROKER_URL", "redis://localhost:6379/0"),
        "result_backend": os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1"),
        # Redis connection settings
        "redis_max_connections": int(os.getenv("REDIS_MAX_CONNECTIONS", "20")),
        "redis_socket_timeout": 120.0,
        "redis_socket_connect_timeout": 5.0,
        "redis_retry_on_timeout": True,
        "redis_socket_keepalive": True,
        # Chord settings for Redis
        "result_chord_join_timeout": 60.0,
        "result_chord_retry_interval": 0.5,
        # Task settings
        "result_expires": 3600,  # 1 hour
        "result_compression": "gzip",
        "worker_prefetch_multiplier": 4,
        "task_acks_late": True,
        "task_track_started": True,
    }


def get_production_redis_urls() -> Dict[str, str]:
    """Get production Redis URLs based on environment."""
    # Default local development
    if not os.getenv("ENVIRONMENT") or os.getenv("ENVIRONMENT") == "development":
        return {
            "broker_url": "redis://localhost:6379/0",
            "result_backend": "redis://localhost:6379/1",
        }

    # Cloud Redis configurations
    redis_host = os.getenv("REDIS_HOST", "localhost")
    redis_port = os.getenv("REDIS_PORT", "6379")
    redis_password = os.getenv("REDIS_PASSWORD", "")

    base_url = f"redis://{f':{redis_password}@' if redis_password else ''}{redis_host}:{redis_port}"

    return {"broker_url": f"{base_url}/0", "result_backend": f"{base_url}/1"}

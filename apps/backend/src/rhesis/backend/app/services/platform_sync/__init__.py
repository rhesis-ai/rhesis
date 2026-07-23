"""Local-only platform sync: pull models/endpoints/etc. from a Rhesis platform.

Importing this package populates the resource registry (via ``resources``) and
exposes the orchestration entry point.
"""

from . import resources  # noqa: F401 — side-effect: registers all resources
from .registry import REGISTRY, SyncResource, resolve_order
from .service import run_platform_sync

__all__ = ["REGISTRY", "SyncResource", "resolve_order", "run_platform_sync"]

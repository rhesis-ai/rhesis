"""Registry of syncable resources for the local-only platform sync.

Each syncable resource is a small, uniform :class:`SyncResource` descriptor.
Resource modules under ``resources/`` register themselves at import time, so the
set of things that can be synced grows by adding one descriptor — the router and
the frontend checkbox UI are thin renderers of this registry.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from rhesis.backend.app.schemas.platform_sync import ResourceSyncResult


@dataclass
class SyncContext:
    """State threaded through a single sync run."""

    db: Session
    organization_id: str
    user_id: str
    client: "object"  # PlatformClient (avoids an import cycle with client.py)
    api_key: str = ""  # the pasted platform key (stored on synced rhesis/polyphemus models)
    cache: dict = field(default_factory=dict)


FetchFn = Callable[[SyncContext], List[dict]]
UpsertFn = Callable[[SyncContext, List[dict]], ResourceSyncResult]


@dataclass(frozen=True)
class SyncResource:
    key: str
    label: str
    fetch: FetchFn
    upsert: UpsertFn
    dependencies: Tuple[str, ...] = ()
    description: Optional[str] = None


REGISTRY: Dict[str, SyncResource] = {}


def register(resource: SyncResource) -> None:
    """Add a resource descriptor to the registry (idempotent by key)."""
    REGISTRY[resource.key] = resource


def resolve_order(selected: List[str]) -> List[str]:
    """Return the selected resource keys in dependency order.

    Selecting a resource automatically pulls its dependencies first (e.g.
    ``endpoints`` pulls ``projects``). Raises 422 for an unknown key.
    """
    order: List[str] = []
    seen: set = set()

    def visit(key: str) -> None:
        if key in seen:
            return
        if key not in REGISTRY:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Unknown sync resource '{key}'",
            )
        seen.add(key)
        for dependency in REGISTRY[key].dependencies:
            visit(dependency)
        order.append(key)

    for key in selected:
        visit(key)
    return order

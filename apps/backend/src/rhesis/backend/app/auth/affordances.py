"""Server-driven authorization affordances — attach per-object permitted actions.

Thin router-layer wrapper around the generic resolver. Computes the caller's
effective capability set once per request, then projects it over each object via
:func:`~rhesis.backend.app.auth.capabilities.permitted_actions_for`, setting a
transient ``permitted_actions`` attribute read by a response schema's
``WithPermittedActions`` mixin.

There is no per-resource code here — pass the resource type (the capability
prefix). The same wrapper serves comment today and any future ``:own`` resource
(e.g. experiments).
"""

from __future__ import annotations

from collections.abc import Iterable as IterableABC
from typing import Iterable, Union

from fastapi import Request
from sqlalchemy.orm import Session

from rhesis.backend.app.auth.capabilities import (
    get_all_capabilities,
    permitted_actions_for,
)
from rhesis.backend.app.auth.principal import resolve_principal_from_request
from rhesis.backend.app.auth.rbac import effective_permissions, project_id_from_scope


def _own_gated_actions(resource_type: str) -> set[str]:
    """Actions of *resource_type* that have a ``:own`` variant in the catalog.

    A ``{resource}:{action}:own`` capability means the route enforces ownership
    via ``authorize_object``, so the affordance must require ownership too — the
    plain cap alone (held broadly in the community tier) is insufficient.
    """
    resource = str(resource_type)
    gated: set[str] = set()
    for cap in get_all_capabilities():
        parts = cap.split(":")
        if len(parts) == 3 and parts[0] == resource and parts[2] == "own":
            gated.add(parts[1])
    return gated


def populate_permitted_actions(
    objs: Union[object, Iterable[object], None],
    resource_type: str,
    *,
    current_user: object,
    request: Request,
    db: Session,
):
    """Attach ``permitted_actions`` to one ORM object or an iterable, then return it.

    Single PDP pass: the effective capability set and the resource's ownership-
    gated actions are computed once, then projected over every object with a pure
    in-memory ownership comparison — no N+1.
    """
    if objs is None:
        return objs
    principal = resolve_principal_from_request(current_user, request)
    project_id = project_id_from_scope(db)
    caps = effective_permissions(principal, project_id=project_id, db=db)
    own_gated = _own_gated_actions(resource_type)
    is_collection = isinstance(objs, IterableABC) and not isinstance(objs, (str, bytes))
    items = list(objs) if is_collection else [objs]
    for obj in items:
        obj.permitted_actions = permitted_actions_for(
            caps,
            obj,
            resource_type,
            current_user_id=principal.user_id,
            own_gated_actions=own_gated,
        )
    return objs

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

from typing import Iterable, Union

from fastapi import Request
from sqlalchemy.orm import Session

from rhesis.backend.app.auth.capabilities import permitted_actions_for
from rhesis.backend.app.auth.principal import resolve_principal_from_request
from rhesis.backend.app.auth.rbac import effective_permissions, project_id_from_scope


def populate_permitted_actions(
    objs: Union[object, Iterable[object], None],
    resource_type: str,
    *,
    current_user: object,
    request: Request,
    db: Session,
):
    """Attach ``permitted_actions`` to one ORM object or an iterable, then return it.

    Single PDP pass: the effective capability set is computed once and projected
    over every object with a pure in-memory ownership comparison — no N+1.
    """
    if objs is None:
        return objs
    principal = resolve_principal_from_request(current_user, request)
    project_id = project_id_from_scope(db)
    caps = effective_permissions(principal, project_id=project_id, db=db)
    items = objs if isinstance(objs, (list, tuple)) else [objs]
    for obj in items:
        obj.permitted_actions = permitted_actions_for(
            caps, obj, resource_type, current_user_id=principal.user_id
        )
    return objs

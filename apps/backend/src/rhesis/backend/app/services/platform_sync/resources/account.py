"""Account access resource — mirror the platform user's verification locally.

Polyphemus (and admin) access is gated by ``User.is_verified`` on the *local*
account, not by the model row. This resource copies the verification flag from
the platform account (``GET /users/settings``) so a local dev account can use
Polyphemus the same way the platform account does.

Note: enabling this also grants local admin — ``is_verified`` is a shared gate
(see ``models/user.py``). It is opt-in (unchecked by default) and local-only.
Even once verified, an actual Polyphemus call additionally requires the local
backend's ``JWT_SECRET_KEY`` to match production (the delegation token is
validated by the hosted Polyphemus service) and network access to it.
"""

from __future__ import annotations

import uuid

from rhesis.backend.app import models
from rhesis.backend.app.schemas.platform_sync import ResourceSyncResult

from ..registry import SyncContext, SyncResource, register

_LABEL = "Account access"


def _fetch(ctx: SyncContext) -> list[dict]:
    # /users/settings returns a single object; wrap it to honour the list contract.
    return [ctx.client.get_json("users/settings")]


def _upsert(ctx: SyncContext, records: list[dict]) -> ResourceSyncResult:
    result = ResourceSyncResult(resource="account", label=_LABEL)
    settings = records[0] if records else {}

    user = ctx.db.query(models.User).filter(models.User.id == uuid.UUID(str(ctx.user_id))).first()
    if user is None:
        result.errors.append("Local user not found")
        return result

    # Only elevate (mirror verified → verified); never downgrade a local account.
    if settings.get("is_verified") and not user.is_verified:
        user.is_verified = True
        result.updated += 1
    else:
        result.skipped += 1
    return result


register(
    SyncResource(
        key="account",
        label=_LABEL,
        fetch=_fetch,
        upsert=_upsert,
        description=(
            "Mirror your platform verification to this local account "
            "(clears Polyphemus 'requires access'; also grants local admin)."
        ),
    )
)

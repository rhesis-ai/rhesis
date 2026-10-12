"""Audit events with no row change behind them.

Sign-ins and sign-outs, password resets and changes, token exchanges, denied
requests and exports. Row changes are recorded on their own by
``models/audit_capture.py``.

With ``db`` the entry joins that session's transaction: it commits with the
work it describes, and a failed write fails the request. Without, the audit
sink writes it on a short session of its own and logs a failure instead of
raising. That is for requests whose own transaction rolls back (a denial, a
failed sign-in) and for sign-ins, so a broken audit write cannot lock anyone out.

Nothing is recorded without the audit log installed, outside a request or job,
or for an org that is not entitled (the sink checks).
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from rhesis.backend.app.auth.capabilities import _METHOD_TO_ACTION
from rhesis.backend.app.models.audit_capture import (
    audit_registered,
    session_user_label,
    user_label,
)
from rhesis.backend.app.provenance import ActorType, current_provenance, provenance_of
from rhesis.backend.events.audit_actions import NOT_ACTIONS, audit_action
from rhesis.backend.events.correlation import resolve_ids
from rhesis.backend.events.dispatcher import emit
from rhesis.backend.events.types import AuditRecorded

logger = logging.getLogger(__name__)

SIGNED_IN = "session.signed_in"
SIGNED_OUT = "session.signed_out"
PASSWORD_RESET = "password.reset"
PASSWORD_CHANGED = "password.changed"
TOKEN_EXCHANGED = "token.exchanged"

_MUTATING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def record_audit_event(
    action: str,
    organization_id,
    *,
    db: Optional[Session] = None,
    outcome: str = "success",
    status_code: Optional[int] = None,
    actor_id=None,
    actor_type: ActorType = ActorType.USER,
    actor_label: Optional[str] = None,
    credential_id: Optional[str] = None,
    credential_hint: Optional[str] = None,
    resource_id=None,
    resource_label: Optional[str] = None,
    project_id=None,
) -> None:
    """Record ``action`` in ``organization_id``'s audit log.

    The actor is the request's own unless ``actor_id`` names one: a sign-in
    or a token exchange happens before the request is authenticated. The
    credential comes from the arguments when given, else from the request.
    """
    if not organization_id or not audit_registered():
        return
    provenance = (provenance_of(db) if db is not None else None) or current_provenance()
    if provenance is None:
        return
    if actor_id is None:
        actor_type, actor_id = provenance.actor_type, provenance.actor_id
        credential_id = credential_id or provenance.credential_id
        credential_hint = credential_hint or provenance.credential_hint
        if actor_label is None and db is not None:
            actor_label = session_user_label(db, actor_id)
    trace_id, span_id = resolve_ids()
    event = AuditRecorded(
        occurred_at=datetime.now(timezone.utc),
        organization_id=organization_id,
        project_id=project_id,
        user_id=actor_id,
        trace_id=trace_id,
        span_id=span_id,
        job_id=provenance.job_id,
        entity_id=resource_id,
        source="audit",
        action=action,
        outcome=outcome,
        status_code=status_code,
        actor_type=actor_type,
        actor_credential_id=credential_id,
        actor_credential_hint=credential_hint,
        actor_label=actor_label,
        channel=provenance.channel,
        ip=provenance.ip,
        user_agent=provenance.user_agent,
        request_id=provenance.request_id,
        resource_label=resource_label,
    )
    emit(event, db=db)


def record_user_event(
    action: str,
    user,
    *,
    db: Optional[Session] = None,
    outcome: str = "success",
    status_code: Optional[int] = None,
) -> None:
    """``action`` by ``user`` on their own account, in their org.

    Reads the row's attributes, so call it before a commit expires them.
    """
    record_audit_event(
        action,
        user.organization_id,
        db=db,
        outcome=outcome,
        status_code=status_code,
        actor_id=user.id,
        actor_label=user_label(user.name, user.email),
        resource_id=user.id,
        resource_label=user.email,
    )


def record_failed_sign_in(db: Session, email: str, *, organization_id=None) -> None:
    """A failed sign-in, in the org of the account ``email`` names.

    An email with no account writes nothing: there is no org to put it in, and
    an entry would tell its readers which addresses were tried. With
    ``organization_id`` (SSO), an account in another org counts as unknown.
    Written on its own session, so a failed write is logged, not raised; so is
    a failed lookup.
    """
    from rhesis.backend.app.crud.user import get_user_by_email

    if not email or not audit_registered():
        return
    try:
        user = get_user_by_email(db, email)
    except Exception:
        logger.exception("Could not look up the account for a failed sign-in")
        return
    if user is None or user.organization_id is None:
        return
    if organization_id is not None and str(user.organization_id) != str(organization_id):
        return
    record_user_event(SIGNED_IN, user, outcome="failure", status_code=401)


def denied_action(capability: str, method: str) -> str:
    """The action a denied request was attempting: the route capability's
    resource and verb, or the HTTP verb when the capability is a bundle."""
    resource, verb = capability.split(":")[:2]
    if verb in NOT_ACTIONS:
        verb = _METHOD_TO_ACTION[method]
    return audit_action(f"{resource}:{verb}")


def record_denial(capability: str, method: str, user, project_id=None) -> None:
    """A 403 from the authorization backstop, on a request that changes something.

    Written on its own session: the request's transaction rolls back. Denied
    reads are not recorded.
    """
    if method not in _MUTATING_METHODS:
        return
    record_audit_event(
        denied_action(capability, method),
        user.organization_id,
        outcome="denied",
        status_code=403,
        actor_label=user_label(user.name, user.email),
        project_id=project_id,
    )

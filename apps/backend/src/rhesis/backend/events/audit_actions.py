"""Audit action names, derived from the capability catalog.

An action reads as what happened, ``resource.verb_past``: the capability
``endpoint:update`` becomes ``endpoint.updated``. The catalog stays the one
list of what can happen; this module only knows how to put a verb in the past
tense. A catalog verb missing from :data:`PAST_TENSE` fails
``tests/backend/events/test_audit_actions.py``, so a new verb gets its audit
name decided once, here.

In core rather than ``ee/audit/`` because the change-capture listeners in
``models/scope_events.py`` name their events, and core never imports EE.
"""

from typing import Iterable

PAST_TENSE: dict[str, str] = {
    "cancel": "cancelled",
    "create": "created",
    "delete": "deleted",
    "execute": "executed",
    "export": "exported",
    "generate": "generated",
    "import": "imported",
    "purge": "purged",
    "react": "reacted",
    "read": "viewed",
    "request": "requested",
    "restore": "restored",
    "update": "updated",
    "use": "used",
    "view": "viewed",
}

# A permission bundle, not something that happens.
NOT_ACTIONS: frozenset[str] = frozenset({"manage"})
# What a ``manage`` bundle covers, so its row changes have names (``role.created``).
MANAGE_VERBS: tuple[str, ...] = ("create", "update", "delete")

# Moments no capability describes.
AUDIT_ONLY_ACTIONS: frozenset[str] = frozenset(
    {
        "audit_log.purged",
        # Superuser only; no capability grants it.
        "organization.deleted",
        "password.changed",
        "password.reset",
        "session.signed_in",
        "session.signed_out",
        "token.exchanged",
    }
)


def capability_verb(capability: str) -> str:
    """The verb of ``resource:verb`` or ``resource:verb:qualifier``."""
    parts = capability.split(":")
    if len(parts) not in (2, 3) or not all(parts):
        raise ValueError(f"not a capability: {capability!r}")
    return parts[1]


def audit_action(capability: str) -> str:
    """``endpoint:update`` -> ``endpoint.updated``.

    A qualifier is dropped (``comment:update:own`` -> ``comment.updated``):
    the entry records what happened, not which grant allowed it.
    """
    resource = capability.split(":", 1)[0]
    verb = capability_verb(capability)
    if verb in NOT_ACTIONS:
        raise ValueError(f"{capability!r} is a permission bundle, not an audit action")
    past = PAST_TENSE.get(verb)
    if past is None:
        raise ValueError(f"no past tense for verb {verb!r} in {capability!r}; add it to PAST_TENSE")
    return f"{resource}.{past}"


def known_actions(capabilities: Iterable[str]) -> frozenset[str]:
    """Every action the audit log can hold, for this capability catalog."""
    derived = set()
    for capability in capabilities:
        if capability_verb(capability) in NOT_ACTIONS:
            resource = capability.split(":", 1)[0]
            derived |= {audit_action(f"{resource}:{verb}") for verb in MANAGE_VERBS}
        else:
            derived.add(audit_action(capability))
    return frozenset(derived) | AUDIT_ONLY_ACTIONS

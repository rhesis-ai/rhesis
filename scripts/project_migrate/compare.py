"""Payload building and comparison shared by every entity step."""

from __future__ import annotations

import hashlib
import json
from typing import Any

# Never copied: identity, ownership and server-computed fields. Users differ per instance and
# the backend rejects foreign user ids with 400.
DROP_ALWAYS = frozenset(
    {
        "id",
        "nano_id",
        "organization_id",
        "user_id",
        "owner_id",
        "assignee_id",
        "status_id",
        "created_at",
        "updated_at",
        "counts",
        "tags",
        "owner",
        "assignee",
        "user",
        "status",
        "organization",
        "project",
        "project_id",
    }
)


def clean(d: dict, allowed: set[str], extra_drop: frozenset[str] = frozenset()) -> dict:
    """Keep the fields the target's create schema accepts, minus identity and None values."""
    return {
        k: v
        for k, v in d.items()
        if k in allowed and k not in DROP_ALWAYS and k not in extra_drop and v is not None
    }


def subset_equal(want: Any, have: Any) -> bool:
    """True if every key in `want` matches `have`. The server may add keys we never send."""
    if isinstance(want, dict):
        if not isinstance(have, dict):
            return False
        return all(subset_equal(v, have.get(k)) for k, v in want.items())
    if isinstance(want, float) or isinstance(have, float):
        try:
            return float(want) == float(have)
        except (TypeError, ValueError):
            return False
    return want == have


def values_equal(want: Any, have: Any) -> bool:
    """Exact match, so a key removed from a dict on the source counts as a change."""
    if isinstance(want, dict):
        return (
            isinstance(have, dict)
            and want.keys() == have.keys()
            and all(values_equal(v, have[k]) for k, v in want.items())
        )
    if isinstance(want, list):
        return (
            isinstance(have, list)
            and len(want) == len(have)
            and all(values_equal(a, b) for a, b in zip(want, have, strict=True))
        )
    if isinstance(want, float) or isinstance(have, float):
        try:
            return float(want) == float(have)
        except (TypeError, ValueError):
            return False
    return want == have


# Fields the server writes its own keys into, so only the keys we send are compared.
SERVER_EXTENDED_FIELDS = frozenset({"endpoint_metadata"})


def changed_fields(want: dict, have: dict) -> list[str]:
    """Top-level fields of `want` that differ on the target. Fields the target has but `want`
    lacks are ignored: the server adds many (ids, nested objects, counts)."""
    return [
        k
        for k, v in want.items()
        if not (
            subset_equal(v, have.get(k))
            if k in SERVER_EXTENDED_FIELDS
            else values_equal(v, have.get(k))
        )
    ]


def lookup_value(obj: Any) -> Any:
    """Type lookups come back as nested objects. We send and compare the type_value string."""
    if isinstance(obj, dict):
        return obj.get("type_value")
    return obj


def name_of(obj: Any) -> str | None:
    return obj.get("name") if isinstance(obj, dict) else None


def test_fingerprint(test: dict, prompt: dict | None) -> str:
    """Natural key of a test, for matching when the state file has no entry for it."""
    blob = json.dumps(
        [
            (prompt or {}).get("content"),
            (prompt or {}).get("expected_response"),
            name_of(test.get("requirement")),
            name_of(test.get("topic")),
            name_of(test.get("category")),
            test.get("test_parameters") or None,
            test.get("test_metadata") or None,
            test.get("test_configuration") or None,
        ],
        sort_keys=True,
        ensure_ascii=False,
        default=str,
    )
    return hashlib.sha256(blob.encode()).hexdigest()

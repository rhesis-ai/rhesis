"""Unit tests for ``hit_post_parse_limit``.

The post-parse limiter is the throttle the token-exchange router
hits *after* the body is parsed (so we can key on ``client_id`` /
``audience`` rather than only on the source IP). Because slowapi's
decorator runs before any handler-side code, this helper is the
only sanctioned mechanism for that.

We exercise it against the real shared limiter (memory storage by
default in the test environment) so the tests pin the actual
behaviour callers depend on.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException

from rhesis.backend.app.utils.rate_limit import hit_post_parse_limit


def _unique_key() -> str:
    """Per-test key so concurrent runs / retries don't share counters."""
    return uuid.uuid4().hex


def test_first_hit_does_not_raise() -> None:
    hit_post_parse_limit(
        "5/minute", namespace="post-parse-test", key=_unique_key()
    )


def test_repeated_hits_under_limit_pass() -> None:
    key = _unique_key()
    for _ in range(5):
        hit_post_parse_limit("5/minute", namespace="post-parse-test", key=key)


def test_exceeding_limit_raises_429() -> None:
    key = _unique_key()
    # Burn the budget.
    for _ in range(3):
        hit_post_parse_limit("3/minute", namespace="post-parse-test", key=key)

    with pytest.raises(HTTPException) as exc:
        hit_post_parse_limit(
            "3/minute", namespace="post-parse-test", key=key
        )
    assert exc.value.status_code == 429
    # The detail string is intentionally generic so a 429 cannot serve
    # as an oracle for whether the keying value (e.g. a particular
    # client_id) exists.
    assert exc.value.detail == "Too many requests"


def test_distinct_keys_have_independent_counters() -> None:
    """The throttle MUST be per-(namespace, key); cross-key bleed is a bug."""
    key_a = _unique_key()
    key_b = _unique_key()
    # Burn key_a's budget.
    for _ in range(3):
        hit_post_parse_limit("3/minute", namespace="post-parse-test", key=key_a)
    with pytest.raises(HTTPException):
        hit_post_parse_limit("3/minute", namespace="post-parse-test", key=key_a)
    # key_b must still be permitted.
    hit_post_parse_limit("3/minute", namespace="post-parse-test", key=key_b)


def test_distinct_namespaces_have_independent_counters() -> None:
    """Two endpoints keyed on the same value must not share a counter."""
    shared_key = _unique_key()
    for _ in range(3):
        hit_post_parse_limit("3/minute", namespace="ns-a", key=shared_key)
    with pytest.raises(HTTPException):
        hit_post_parse_limit("3/minute", namespace="ns-a", key=shared_key)
    # ns-b's counter for the same key starts fresh.
    hit_post_parse_limit("3/minute", namespace="ns-b", key=shared_key)

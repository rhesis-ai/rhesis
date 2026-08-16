"""Shared test-type resolution used by schema validation and bulk creation.

Single source of truth for the effective-type precedence:

1. the test's explicit ``test_type``
2. auto-detection from content (a ``goal`` key in ``test_configuration`` means
   Multi-Turn, a ``prompt`` means Single-Turn)
3. the parent test set's type
4. the configured default

The bulk-create schema validator and ``bulk_create_tests`` must both resolve
through this helper — two copies will drift, and a drift reintroduces exactly
the set-vs-test type mismatch this guards against.
"""

from typing import Any, Dict, Optional

from rhesis.backend.app.constants import TestSetType, TestType


def resolve_effective_test_type(
    explicit_test_type: Optional[Any] = None,
    test_configuration: Optional[Dict[str, Any]] = None,
    prompt: Optional[Any] = None,
    test_set_type: Optional[Any] = None,
    default_test_type: Optional[Any] = None,
) -> Optional[str]:
    """Resolve a test's effective type via the documented precedence.

    Returns None when nothing pins a type.
    """
    if explicit_test_type:
        return TestType.get_value(explicit_test_type)
    if test_configuration and isinstance(test_configuration, dict) and "goal" in test_configuration:
        return TestType.MULTI_TURN.value
    if prompt:
        return TestType.SINGLE_TURN.value
    parent_type = TestSetType.get_value(test_set_type) if test_set_type else None
    return parent_type or TestType.get_value(default_test_type)

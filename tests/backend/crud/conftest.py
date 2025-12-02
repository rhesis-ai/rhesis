"""
🔧 CRUD Test Fixtures

Shared fixtures and utilities for CRUD operation testing.
Uses existing data factories and database fixtures instead of custom implementations.
"""

import pytest

# Import existing data factories
from tests.backend.routes.fixtures.data_factories import (
    TagDataFactory,
    TestDataFactory,
    TokenDataFactory,
    MetricDataFactory,
    BehaviorDataFactory,
    PromptDataFactory,
)

# Import existing entity fixtures
from tests.backend.routes.fixtures.entities import (
    db_test,
    db_test_with_prompt,
    db_test_minimal,
    db_prompt,
    db_user,
    db_status,
    test_organization,
)

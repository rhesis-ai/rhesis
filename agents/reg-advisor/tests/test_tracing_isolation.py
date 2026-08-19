"""Architecture guard: tracing must stay at the entrypoints only.

``docs/architecture.md`` promises that the regulatory business modules stay free
of framework-boundary concerns, so tracing can be added (and removed) at the
entrypoints without touching the classifier, the knowledge base, the state model
or the safety rules. This test is what keeps that promise true: it fails if the
Rhesis SDK leaks downward into a business module.

The one deliberate exception is ``session.py``, which needs to mark a
conversation turn so the Google ADK integration can group turns. It imports the
*light* ``rhesis.telemetry`` package rather than the SDK, which is a contextvar
module with no client, no HTTP and no OTEL provider ownership.
"""

from __future__ import annotations

import inspect

import pytest

from reg_advisor import (
    classify,
    client,
    knowledge,
    runner,
    safety,
    session,
    state,
    terminals,
    tools,
    utils,
)
from reg_advisor.agents import briefing, budget, coordinator, critic, intake

BUSINESS_MODULES = [
    classify,
    client,
    knowledge,
    runner,
    safety,
    state,
    terminals,
    tools,
    utils,
    briefing,
    budget,
    coordinator,
    critic,
    intake,
]


@pytest.mark.parametrize("module", BUSINESS_MODULES, ids=lambda m: m.__name__)
def test_business_modules_do_not_import_the_sdk(module):
    source = inspect.getsource(module)
    assert "rhesis.sdk" not in source, f"{module.__name__} imports the Rhesis SDK"
    assert "from rhesis import" not in source, f"{module.__name__} imports rhesis"


def test_session_uses_the_light_telemetry_package_only():
    """Conversation grouping needs a contextvar, not the whole SDK."""
    source = inspect.getsource(session)
    assert "rhesis.telemetry.context" in source
    assert "rhesis.sdk" not in source


def test_app_is_the_only_module_importing_the_sdk():
    from reg_advisor import app

    assert "from rhesis.sdk import" in inspect.getsource(app)


def test_state_has_no_framework_imports_at_all():
    """The state model is plain pydantic; it must not know about ADK or Rhesis."""
    source = inspect.getsource(state)
    assert "google.adk" not in source
    assert "rhesis" not in source

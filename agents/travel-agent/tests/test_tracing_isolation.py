"""Architecture guard: telemetry stays at the edges.

``app.py`` owns the Rhesis SDK. Everything below it is plain MAF plus the light
``rhesis.telemetry`` package, which is stdlib-only and carries none of the SDK's
dependency weight. Without this test the boundary erodes one import at a time.
"""

from __future__ import annotations

import inspect

import pytest

from travel_agent import (
    brief,
    faults,
    router,
    runner,
    safety,
    session,
    state,
    utils,
    workflow,
)
from travel_agent.agents import base as agents_base
from travel_agent.agents import coordinator, specialists
from travel_agent.tools import base as tools_base
from travel_agent.tools import dining, lodging, places, routing, sights, surprise

# Every module that must never reach for the Rhesis SDK.
BUSINESS_MODULES = [
    agents_base,
    brief,
    coordinator,
    dining,
    faults,
    lodging,
    places,
    router,
    routing,
    runner,
    safety,
    sights,
    specialists,
    state,
    surprise,
    tools_base,
    utils,
    workflow,
]


@pytest.mark.parametrize("module", BUSINESS_MODULES, ids=lambda m: m.__name__)
def test_business_modules_do_not_import_the_rhesis_sdk(module):
    source = inspect.getsource(module)
    assert "rhesis.sdk" not in source
    assert "from rhesis import" not in source


def test_session_uses_the_light_telemetry_package_only():
    """``rhesis.telemetry`` is the stdlib-weight package; ``rhesis.sdk`` drags in the world."""
    source = inspect.getsource(session)
    assert "rhesis.telemetry.context" in source
    assert "rhesis.sdk" not in source


def test_state_has_no_framework_imports_at_all():
    """The brief must be reasonable about without running an agent."""
    source = inspect.getsource(state)
    assert "agent_framework" not in source
    assert "rhesis" not in source


def test_app_is_the_only_module_importing_the_sdk():
    from travel_agent import app

    assert "from rhesis.sdk import" in inspect.getsource(app)

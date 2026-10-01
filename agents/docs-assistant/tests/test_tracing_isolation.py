"""Architecture guard: the Rhesis SDK stays at the edges.

Tracing can be added or removed at the entry points without touching the routing, retrieval,
grounding or safety code. This fails if the SDK leaks into a business module.

Two deliberate exceptions: ``tracing.py`` is the bridge, and ``session.py`` marks the turn root,
which needs only the light ``rhesis.telemetry`` package (a contextvar module with no client,
no HTTP and no provider of its own).
"""

from __future__ import annotations

import inspect

import pytest

from docs_assistant import (
    compose,
    config,
    context,
    grounding,
    models,
    runner,
    safety,
    schemas,
    session,
    state,
    terminals,
    tools,
)
from docs_assistant.agents import answerer, critic, triage
from docs_assistant.corpus import cache, changelog, fetcher, index, mirror, parser

BUSINESS_MODULES = [
    compose,
    config,
    context,
    grounding,
    models,
    runner,
    safety,
    schemas,
    state,
    terminals,
    tools,
    answerer,
    critic,
    triage,
    cache,
    changelog,
    fetcher,
    index,
    mirror,
    parser,
]


@pytest.mark.parametrize("module", BUSINESS_MODULES, ids=lambda m: m.__name__)
def test_business_modules_do_not_import_rhesis(module):
    source = inspect.getsource(module)
    assert "rhesis.sdk" not in source, f"{module.__name__} imports the Rhesis SDK"
    assert "rhesis.telemetry" not in source, f"{module.__name__} imports Rhesis telemetry"
    assert "from rhesis import" not in source, f"{module.__name__} imports rhesis"


def test_session_uses_the_light_telemetry_package_only():
    source = inspect.getsource(session)
    assert "from rhesis.telemetry" in source
    assert "rhesis.sdk" not in source


def test_only_the_app_and_the_bridge_import_the_sdk():
    from docs_assistant import app, tracing

    assert "from rhesis.sdk import" in inspect.getsource(app)
    assert "from rhesis.sdk" in inspect.getsource(tracing)

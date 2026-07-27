"""Regression guard: business modules must not import Rhesis tracing."""

from __future__ import annotations

import inspect

from tests.mocks import make_components
from visit_prep import pipeline, session
from visit_prep.pipeline import build_intent_pipeline, run_turn


def test_pipeline_has_no_tracer_node():
    pipe = build_intent_pipeline(make_components([]))
    assert not pipe.graph.has_node("tracer")


def test_run_turn_has_no_session_id_param():
    sig = inspect.signature(run_turn)
    assert "session_id" not in sig.parameters


def test_build_intent_pipeline_has_no_enable_tracing_param():
    sig = inspect.signature(build_intent_pipeline)
    assert "enable_tracing" not in sig.parameters


def test_pipeline_source_has_no_tracing_imports():
    source = inspect.getsource(pipeline)
    assert "haystack_integrations" not in source
    assert "from rhesis" not in source
    assert "import rhesis" not in source


def test_session_source_has_no_tracing_imports():
    source = inspect.getsource(session)
    assert "haystack_integrations" not in source
    assert "from rhesis" not in source
    assert "import rhesis" not in source

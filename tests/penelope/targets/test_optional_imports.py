"""Regression test: rhesis.penelope.targets must import without optional deps.

langchain, langgraph, pydantic-ai, and the agent-framework packages are all
optional dependencies of rhesis-penelope (see penelope/pyproject.toml).
LangChainTarget, LangGraphTarget, PydanticAITarget, and MAFTarget are imported
unconditionally from targets/__init__.py, so none of their modules may import
those optional packages at module level - only inside the functions that
actually need them.
"""

import builtins
import sys

import pytest

_BLOCKED = {"langchain_core", "langgraph", "pydantic_ai", "agent_framework"}


@pytest.fixture
def block_optional_deps(monkeypatch):
    """Make imports of langchain_core/langgraph/pydantic_ai raise ImportError,
    and drop any already-imported rhesis.penelope modules so the next import
    is forced to go through the (now-blocked) optional packages fresh.
    """
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name.split(".")[0] in _BLOCKED:
            raise ImportError(f"simulated: {name} not installed")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    removed = {}
    for mod_name in list(sys.modules):
        if mod_name.split(".")[0] in _BLOCKED or mod_name.startswith("rhesis.penelope"):
            removed[mod_name] = sys.modules.pop(mod_name)

    yield

    sys.modules.update(removed)


def test_targets_package_imports_without_optional_deps(block_optional_deps):
    import rhesis.penelope.targets as targets

    assert targets.EndpointTarget is not None
    assert targets.LangChainTarget is not None
    assert targets.LangGraphTarget is not None
    assert targets.PydanticAITarget is not None
    assert targets.MAFTarget is not None


def test_endpoint_target_usable_without_optional_deps(block_optional_deps):
    from unittest.mock import Mock

    from rhesis.penelope.targets import EndpointTarget

    endpoint = Mock()
    endpoint.id = "endpoint-123"
    endpoint.fields = {"name": "Test", "url": "https://test.com"}

    target = EndpointTarget(endpoint=endpoint)
    assert target.target_id == "endpoint-123"

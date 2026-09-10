"""Tests that disabling an integration undoes what enabling it patched.

Both integrations instrument by replacing methods on classes they do not own -
``CompiledStateGraph`` for graph entry points, ``BaseTool`` for tool calls - so
without a working unpatch path a disabled integration keeps injecting its
callback into every graph and tool in the process.
"""

import pytest
from langchain_core.tools import BaseTool
from langgraph.graph.state import CompiledStateGraph

from rhesis.sdk.telemetry.integrations.langchain import (
    get_integration as langchain_integration,
)
from rhesis.sdk.telemetry.integrations.langchain.utils import (
    ToolPatchState,
    restore_class_method,
)
from rhesis.sdk.telemetry.integrations.langgraph import (
    GraphPatchState,
    LangGraphIntegration,
)

GRAPH_METHODS = ("invoke", "ainvoke", "stream", "astream")
TOOL_METHODS = ("invoke", "ainvoke")


def snapshot(cls, names) -> dict:
    """What a class looks like now: the resolved method and where it lives."""
    return {name: (getattr(cls, name, None), name in cls.__dict__) for name in names}


@pytest.fixture(autouse=True)
def leave_no_trace():
    """Guarantee these tests cannot themselves leave a patch behind."""
    graph_before = snapshot(CompiledStateGraph, GRAPH_METHODS)
    tool_before = snapshot(BaseTool, TOOL_METHODS)
    GraphPatchState.reset()
    yield
    LangGraphIntegration().disable()
    langchain_integration().disable()
    GraphPatchState.reset()
    ToolPatchState.reset()
    assert snapshot(CompiledStateGraph, GRAPH_METHODS) == graph_before
    assert snapshot(BaseTool, TOOL_METHODS) == tool_before


class TestDisableRestoresTheClasses:
    def test_graph_entry_points_come_back_exactly(self):
        before = snapshot(CompiledStateGraph, GRAPH_METHODS)

        integration = LangGraphIntegration()
        integration.enable()
        assert snapshot(CompiledStateGraph, GRAPH_METHODS) != before, "enable should patch"

        integration.disable()
        assert snapshot(CompiledStateGraph, GRAPH_METHODS) == before

    def test_inherited_methods_stay_inherited(self):
        """Restoring by assignment would shadow them with a copy of themselves."""
        assert not any(name in CompiledStateGraph.__dict__ for name in GRAPH_METHODS), (
            "precondition: these are inherited, which is what makes this worth checking"
        )

        integration = LangGraphIntegration()
        integration.enable()
        integration.disable()

        assert not any(name in CompiledStateGraph.__dict__ for name in GRAPH_METHODS)

    def test_tool_invocation_comes_back_exactly(self):
        before = snapshot(BaseTool, TOOL_METHODS)

        LangGraphIntegration().enable()
        assert snapshot(BaseTool, TOOL_METHODS) != before, "enable should patch"

        langchain_integration().disable()
        assert snapshot(BaseTool, TOOL_METHODS) == before

    def test_own_methods_stay_owned(self):
        """The mirror of the inherited case: BaseTool defines these itself."""
        assert all(name in BaseTool.__dict__ for name in TOOL_METHODS), (
            "precondition: BaseTool owns these"
        )

        LangGraphIntegration().enable()
        langchain_integration().disable()

        assert all(name in BaseTool.__dict__ for name in TOOL_METHODS)

    def test_patch_state_is_forgotten(self):
        LangGraphIntegration().enable()
        assert GraphPatchState.get_invoke() is not None

        LangGraphIntegration().disable()
        assert GraphPatchState.get_invoke() is None
        assert GraphPatchState.is_done() is False


class TestDisableReleasesTheTracingVariable:
    """``enable()`` also advertises the callback through LangSmith's context variable.

    Left set, LangChain keeps adding that handler to callback managers, so a
    disabled integration goes on tracing everything alongside whoever else is
    tracing - which is how it reparented spans in unrelated test modules.
    """

    def test_the_variable_is_handed_back(self):
        from langchain_core.tracers.context import tracing_v2_callback_var

        assert tracing_v2_callback_var.get() is None, "precondition: unclaimed"

        integration = LangGraphIntegration()
        integration.enable()
        assert tracing_v2_callback_var.get() is integration._callback

        integration.disable()
        assert tracing_v2_callback_var.get() is None

    def test_a_different_instance_can_release_it(self):
        """Teardown rarely holds the instance that enabled."""
        from langchain_core.tracers.context import tracing_v2_callback_var

        LangGraphIntegration().enable()
        assert tracing_v2_callback_var.get() is not None

        LangGraphIntegration().disable()
        assert tracing_v2_callback_var.get() is None

    def test_a_foreign_claim_is_left_alone(self):
        """Something else may have taken the variable since we set it."""
        from langchain_core.tracers.context import tracing_v2_callback_var

        LangGraphIntegration().enable()

        someone_else = object()
        tracing_v2_callback_var.set(someone_else)
        LangGraphIntegration().disable()

        assert tracing_v2_callback_var.get() is someone_else
        tracing_v2_callback_var.set(None)


class TestEnableAfterDisable:
    def test_a_second_enable_patches_again(self):
        """Disable clears the "already patched" guard, so enable still works."""
        first = LangGraphIntegration()
        first.enable()
        first.disable()

        second = LangGraphIntegration()
        assert second.enable() is True
        assert GraphPatchState.get_invoke() is not None
        assert CompiledStateGraph.invoke is not GraphPatchState.get_invoke()

    def test_cycling_does_not_stack_patches(self):
        """Each disable has to undo exactly one enable, or the wrappers nest."""
        before = snapshot(CompiledStateGraph, GRAPH_METHODS)

        for _ in range(3):
            integration = LangGraphIntegration()
            integration.enable()
            integration.disable()

        assert snapshot(CompiledStateGraph, GRAPH_METHODS) == before


class TestRestoreClassMethod:
    """The helper both integrations restore through."""

    def test_removes_an_override_of_an_inherited_method(self):
        class Base:
            def run(self):
                return "base"

        class Child(Base):
            pass

        original = Child.run
        Child.run = lambda self: "patched"
        restore_class_method(Child, "run", original)

        assert Child.run is original
        assert "run" not in Child.__dict__, "an inherited method must stay inherited"

    def test_reinstates_a_method_the_class_owned(self):
        class Owner:
            def run(self):
                return "own"

        original = Owner.run
        Owner.run = lambda self: "patched"
        restore_class_method(Owner, "run", original)

        assert Owner.run is original
        assert "run" in Owner.__dict__, "an own method must stay owned"

    def test_is_a_no_op_when_nothing_was_patched(self):
        class Owner:
            def run(self):
                return "own"

        original = Owner.run
        restore_class_method(Owner, "run", original)

        assert Owner.run is original
        assert "run" in Owner.__dict__

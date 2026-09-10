"""Tests for the span bookkeeping behind the LangChain callback.

Covers what the registry has to get right on its own: parenting across skipped
runs, resolving which agent a run sits inside, and staying bounded when runs
never report completion.
"""

import threading

import pytest

from rhesis.sdk.telemetry.integrations.langchain.span_registry import (
    MAX_TRACKED_RUNS,
    SpanRegistry,
    execution_ident,
)


class FakeSpan:
    """Stands in for a span where only end/status behaviour matters."""

    def __init__(self, name: str = "span") -> None:
        self.name = name
        self.ended = False
        self.status = None

    def set_status(self, status) -> None:
        self.status = status

    def end(self) -> None:
        self.ended = True


@pytest.fixture
def registry():
    return SpanRegistry()


def track(registry: SpanRegistry, run_id: str, parent_key=None) -> FakeSpan:
    span = FakeSpan(run_id)
    registry.track(run_id, span, parent_key)
    return span


class TestClaiming:
    def test_a_run_is_claimed_once(self, registry):
        assert registry.claim("run-1") is True
        assert registry.claim("run-1") is False

    def test_is_claimed_reports_without_claiming(self, registry):
        assert registry.is_claimed("run-1") is False
        registry.claim("run-1")
        assert registry.is_claimed("run-1") is True

    def test_ending_a_run_releases_its_claim(self, registry):
        registry.claim("run-1")
        track(registry, "run-1")
        registry.end("run-1")
        assert registry.claim("run-1") is True

    def test_concurrent_claims_yield_one_winner(self, registry):
        """The check and the claim have to be one step."""
        start = threading.Barrier(8)
        won = []

        def contend():
            start.wait(timeout=5)
            if registry.claim("contended"):
                won.append(threading.get_ident())

        threads = [threading.Thread(target=contend) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert len(won) == 1


class TestParenting:
    def test_child_parents_to_a_tracked_run(self, registry):
        parent_span = track(registry, "parent")
        context, key = registry.resolve_parent("parent")
        assert key == "parent"
        assert context is not None
        assert parent_span.ended is False

    def test_a_run_with_no_parent_resolves_to_nothing(self, registry):
        assert registry.resolve_parent(None) == (None, None)

    def test_skipped_runs_pass_their_parent_down(self, registry):
        """A child of an untraced step still belongs to the node containing it."""
        track(registry, "node")
        registry.skip("lcel-step", "node")

        _context, key = registry.resolve_parent("lcel-step")
        assert key == "node"

    def test_an_ended_parent_no_longer_parents(self, registry):
        track(registry, "parent")
        registry.end("parent")
        assert registry.resolve_parent("parent") == (None, None)


class TestEnclosingAgent:
    def test_found_through_ancestry(self, registry):
        track(registry, "agent-run")
        registry.push_agent("agent-run", "researcher")
        track(registry, "llm-run", parent_key="agent-run")

        assert registry.enclosing_agent("agent-run") == "researcher"

    def test_found_through_a_skipped_intermediate(self, registry):
        track(registry, "agent-run")
        registry.push_agent("agent-run", "researcher")
        registry.skip("inner-step", "agent-run")

        assert registry.enclosing_agent("inner-step") == "researcher"

    def test_falls_back_to_this_execution_when_there_is_no_parent(self, registry):
        """Tools reached through the patched BaseTool.invoke have no parent."""
        registry.push_agent("agent-run", "researcher")
        assert registry.enclosing_agent(None) == "researcher"

    def test_another_execution_does_not_leak_its_agent(self, registry):
        registry.push_agent("agent-run", "researcher")

        seen = {}

        def elsewhere():
            seen["agent"] = registry.enclosing_agent(None)

        thread = threading.Thread(target=elsewhere)
        thread.start()
        thread.join(timeout=5)

        assert seen["agent"] is None

    def test_popping_unstacks_the_agent(self, registry):
        registry.push_agent("agent-run", "researcher")
        registry.pop_agent("agent-run")
        assert registry.enclosing_agent(None) is None

    def test_nested_agents_unstack_out_of_order(self, registry):
        registry.push_agent("outer", "orchestrator")
        registry.push_agent("inner", "specialist")

        registry.pop_agent("outer")
        # The inner agent is still running and still the innermost one.
        assert registry.enclosing_agent(None) == "specialist"

        registry.pop_agent("inner")
        assert registry.enclosing_agent(None) is None

    def test_the_stack_map_does_not_grow_per_execution(self, registry):
        """Or a long-lived process keeps an entry per thread it ever used."""

        def push_and_pop():
            registry.push_agent(f"run-{threading.get_ident()}", "agent")
            registry.pop_agent(f"run-{threading.get_ident()}")

        for _ in range(20):
            thread = threading.Thread(target=push_and_pop)
            thread.start()
            thread.join(timeout=5)

        assert registry._agent_stacks == {}


class TestStaysBounded:
    """Runs that never report completion must not accumulate forever."""

    def test_skipped_run_tracking_is_capped(self, registry):
        for i in range(MAX_TRACKED_RUNS + 100):
            registry.skip(f"run-{i}")

        assert len(registry._skipped_parents) <= MAX_TRACKED_RUNS

    def test_open_span_tracking_is_capped(self, registry):
        for i in range(MAX_TRACKED_RUNS + 50):
            track(registry, f"run-{i}")

        assert len(registry._spans) <= MAX_TRACKED_RUNS

    def test_an_evicted_span_is_ended_so_it_still_exports(self, registry):
        oldest = track(registry, "run-oldest")
        for i in range(MAX_TRACKED_RUNS):
            track(registry, f"run-{i}")

        assert registry.span_for("run-oldest") is None
        assert oldest.ended, "an evicted span must be ended, or it never exports"
        assert oldest.status is not None, "and say why it was closed"

    def test_eviction_unstacks_the_agent_too(self, registry):
        track(registry, "run-oldest")
        registry.push_agent("run-oldest", "abandoned")
        for i in range(MAX_TRACKED_RUNS):
            track(registry, f"run-{i}")

        assert registry.enclosing_agent(None) != "abandoned"


class TestExecutionIdent:
    def test_distinguishes_threads(self):
        here = execution_ident()
        seen = {}

        def elsewhere():
            seen["ident"] = execution_ident()

        thread = threading.Thread(target=elsewhere)
        thread.start()
        thread.join(timeout=5)

        assert seen["ident"] != here

    def test_is_stable_within_one_thread(self):
        assert execution_ident() == execution_ident()

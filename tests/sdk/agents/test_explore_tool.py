"""Tests for ExploreEndpointTool."""

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from rhesis.sdk.agents.tools import (
    COMPREHENSIVE_STRATEGY_SEQUENCE,
    ExploreEndpointTool,
)
from rhesis.sdk.targets import Target, TargetResponse


class FakeTarget(Target):
    """Minimal Target for testing."""

    def __init__(self, endpoint_id="fake-ep"):
        self._id = endpoint_id

    @property
    def target_type(self):
        return "endpoint"

    @property
    def target_id(self):
        return self._id

    @property
    def description(self):
        return f"Fake endpoint {self._id}"

    def send_message(self, message, conversation_id=None, **kw):
        return TargetResponse(success=True, content=f"Reply to: {message}")

    def validate_configuration(self):
        return True, None


class FakeStatus(Enum):
    COMPLETED = "completed"


@dataclass
class FakeTurnSummary:
    turn: int
    penelope_message: str
    target_response: str


@dataclass
class FakeTestResult:
    status: FakeStatus = FakeStatus.COMPLETED
    goal_achieved: bool = True
    turns_used: int = 3
    findings: str = "The bot handles travel queries."
    goal_evaluation: str = "Goal achieved"
    conversation_summary: List[Any] = field(default_factory=lambda: [
        FakeTurnSummary(1, "What do you do?", "I help with travel."),
        FakeTurnSummary(2, "Can you book flights?", "Yes!"),
        FakeTurnSummary(3, "What about hotels?", "Yes, hotels too."),
    ])


@pytest.mark.unit
class TestExploreEndpointToolInit:
    """Test ExploreEndpointTool initialization modes."""

    def test_requires_endpoint_or_factory(self):
        with pytest.raises(ValueError, match="Must provide"):
            ExploreEndpointTool()

    def test_unbound_mode_with_factory(self):
        factory = lambda eid: FakeTarget(eid)
        tool = ExploreEndpointTool(target_factory=factory)
        assert tool.name == "explore_endpoint"
        assert tool._endpoint is None
        assert tool._target_factory is factory

    def test_unbound_description_mentions_endpoint_id(self):
        tool = ExploreEndpointTool(target_factory=lambda eid: FakeTarget(eid))
        assert "endpoint_id" in tool.description

    def test_unbound_schema_requires_endpoint_id(self):
        tool = ExploreEndpointTool(target_factory=lambda eid: FakeTarget(eid))
        schema = tool.parameters_schema
        assert "endpoint_id" in schema["properties"]
        assert "endpoint_id" in schema["required"]

    def test_bound_schema_does_not_require_endpoint_id(self):
        class FakeEndpoint:
            id = "ep-123"
            name = "Test"
            description = "A test endpoint"

        tool = ExploreEndpointTool(endpoint=FakeEndpoint())
        schema = tool.parameters_schema
        assert "endpoint_id" not in schema.get("properties", {})
        assert "endpoint_id" not in schema["required"]

    def test_requires_confirmation_is_true(self):
        tool = ExploreEndpointTool(target_factory=lambda eid: FakeTarget(eid))
        assert tool.requires_confirmation is True


@pytest.mark.unit
class TestExploreEndpointToolSchema:
    """Test that the schema includes strategy and previous_findings."""

    def test_schema_includes_strategy_param(self):
        tool = ExploreEndpointTool(target_factory=lambda eid: FakeTarget(eid))
        schema = tool.parameters_schema
        assert "strategy" in schema["properties"]
        assert "comprehensive" in schema["properties"]["strategy"]["description"]

    def test_schema_includes_previous_findings_param(self):
        tool = ExploreEndpointTool(target_factory=lambda eid: FakeTarget(eid))
        schema = tool.parameters_schema
        assert "previous_findings" in schema["properties"]

    def test_goal_not_required_when_strategy_available(self):
        tool = ExploreEndpointTool(target_factory=lambda eid: FakeTarget(eid))
        schema = tool.parameters_schema
        assert "goal" not in schema.get("required", [])


@pytest.mark.unit
class TestExploreEndpointToolExecute:
    """Test ExploreEndpointTool.execute() in unbound mode."""

    @pytest.mark.asyncio
    async def test_empty_goal_rejected_without_strategy(self):
        tool = ExploreEndpointTool(target_factory=lambda eid: FakeTarget(eid))
        result = await tool.execute(goal="", endpoint_id="ep-1")
        assert not result.success
        assert "empty" in result.error.lower()

    @pytest.mark.asyncio
    async def test_empty_goal_accepted_with_strategy(self):
        """When a strategy is provided, goal can be empty."""
        tool = ExploreEndpointTool(target_factory=lambda eid: FakeTarget(eid))
        with patch.object(tool, "_run_exploration", return_value=FakeTestResult()):
            with patch.object(tool, "_resolve_strategy") as mock_resolve:
                mock_strategy = MagicMock()
                mock_strategy.name = "domain_probing"
                mock_strategy.recommended_max_turns = 5
                mock_strategy.build_goal.return_value = "Auto goal"
                mock_strategy.build_instructions.return_value = "Auto instructions"
                mock_strategy.format_findings.return_value = {"strategy": "domain_probing"}
                mock_resolve.return_value = mock_strategy

                result = await tool.execute(
                    goal="", endpoint_id="ep-1", strategy="domain_probing"
                )
                assert result.success

    @pytest.mark.asyncio
    async def test_missing_endpoint_id_in_unbound_mode(self):
        tool = ExploreEndpointTool(target_factory=lambda eid: FakeTarget(eid))
        result = await tool.execute(goal="Explore domain")
        assert not result.success
        assert "endpoint" in result.error.lower()

    @pytest.mark.asyncio
    async def test_factory_error_handled(self):
        def bad_factory(eid):
            raise ValueError("endpoint not found")

        tool = ExploreEndpointTool(target_factory=bad_factory)
        result = await tool.execute(goal="Explore", endpoint_id="bad-id")
        assert not result.success
        assert "resolve endpoint" in result.error.lower()

    @pytest.mark.asyncio
    async def test_unknown_strategy_returns_error(self):
        tool = ExploreEndpointTool(target_factory=lambda eid: FakeTarget(eid))
        result = await tool.execute(
            endpoint_id="ep-1", strategy="nonexistent_strategy"
        )
        assert not result.success
        assert "unknown strategy" in result.error.lower()

    @pytest.mark.asyncio
    async def test_backward_compat_goal_only(self):
        """Calling with just goal (no strategy) still works as before."""
        tool = ExploreEndpointTool(target_factory=lambda eid: FakeTarget(eid))
        with patch.object(tool, "_run_exploration", return_value=FakeTestResult()):
            result = await tool.execute(goal="Explore domain", endpoint_id="ep-1")
            assert result.success
            content = json.loads(result.content)
            assert content["status"] == "completed"
            assert content["goal_achieved"] is True

    def test_resolve_target_uses_factory(self):
        created = []

        def factory(eid):
            t = FakeTarget(eid)
            created.append(eid)
            return t

        tool = ExploreEndpointTool(target_factory=factory)
        target = tool._resolve_target("ep-42")
        assert created == ["ep-42"]
        assert target.target_id == "ep-42"

    def test_resolve_target_uses_bound_endpoint(self):
        class FakeEndpoint:
            id = "ep-bound"
            name = "Bound"
            description = ""

        tool = ExploreEndpointTool(endpoint=FakeEndpoint())
        assert tool._endpoint.id == "ep-bound"
        assert tool._endpoint_id == "ep-bound"


@pytest.mark.unit
class TestExploreEndpointToolStrategy:
    """Test strategy-based execution."""

    @pytest.mark.asyncio
    async def test_strategy_generates_goal_and_instructions(self):
        tool = ExploreEndpointTool(target_factory=lambda eid: FakeTarget(eid))

        mock_strategy = MagicMock()
        mock_strategy.name = "domain_probing"
        mock_strategy.recommended_max_turns = 5
        mock_strategy.build_goal.return_value = "Strategy-generated goal"
        mock_strategy.build_instructions.return_value = "Strategy instructions"
        mock_strategy.format_findings.return_value = {"strategy": "domain_probing"}

        with patch.object(tool, "_resolve_strategy", return_value=mock_strategy):
            with patch.object(
                tool, "_run_exploration", return_value=FakeTestResult()
            ) as mock_run:
                result = await tool.execute(
                    endpoint_id="ep-1", strategy="domain_probing"
                )
                assert result.success
                mock_strategy.build_goal.assert_called_once()
                mock_strategy.build_instructions.assert_called_once()
                mock_strategy.format_findings.assert_called_once()
                call_kwargs = mock_run.call_args.kwargs
                assert call_kwargs["goal"] == "Strategy-generated goal"
                assert call_kwargs["instructions"] == "Strategy instructions"

    @pytest.mark.asyncio
    async def test_strategy_with_goal_override(self):
        tool = ExploreEndpointTool(target_factory=lambda eid: FakeTarget(eid))

        mock_strategy = MagicMock()
        mock_strategy.name = "domain_probing"
        mock_strategy.recommended_max_turns = 5
        mock_strategy.build_instructions.return_value = "Auto instructions"
        mock_strategy.format_findings.return_value = {"strategy": "domain_probing"}

        with patch.object(tool, "_resolve_strategy", return_value=mock_strategy):
            with patch.object(
                tool, "_run_exploration", return_value=FakeTestResult()
            ) as mock_run:
                result = await tool.execute(
                    goal="My custom goal",
                    endpoint_id="ep-1",
                    strategy="domain_probing",
                )
                assert result.success
                mock_strategy.build_goal.assert_not_called()
                call_kwargs = mock_run.call_args.kwargs
                assert call_kwargs["goal"] == "My custom goal"

    @pytest.mark.asyncio
    async def test_strategy_passes_previous_findings(self):
        tool = ExploreEndpointTool(target_factory=lambda eid: FakeTarget(eid))
        prev = {"domain": "travel", "purpose": "booking"}

        mock_strategy = MagicMock()
        mock_strategy.name = "capability_mapping"
        mock_strategy.recommended_max_turns = 7
        mock_strategy.build_goal.return_value = "Goal"
        mock_strategy.build_instructions.return_value = "Instructions"
        mock_strategy.format_findings.return_value = {"strategy": "capability_mapping"}

        with patch.object(tool, "_resolve_strategy", return_value=mock_strategy):
            with patch.object(
                tool, "_run_exploration", return_value=FakeTestResult()
            ) as mock_run:
                result = await tool.execute(
                    endpoint_id="ep-1",
                    strategy="capability_mapping",
                    previous_findings=prev,
                )
                assert result.success
                mock_strategy.build_goal.assert_called_once()
                call_args = mock_strategy.build_goal.call_args
                assert call_args.kwargs.get("previous_findings") == prev
                call_kwargs = mock_run.call_args.kwargs
                assert call_kwargs["context"] == prev

    @pytest.mark.asyncio
    async def test_strategy_result_includes_strategy_findings(self):
        tool = ExploreEndpointTool(target_factory=lambda eid: FakeTarget(eid))

        mock_strategy = MagicMock()
        mock_strategy.name = "domain_probing"
        mock_strategy.recommended_max_turns = 5
        mock_strategy.build_goal.return_value = "Goal"
        mock_strategy.build_instructions.return_value = "Instructions"
        mock_strategy.format_findings.return_value = {
            "strategy": "domain_probing",
            "domain": "travel",
        }

        with patch.object(tool, "_resolve_strategy", return_value=mock_strategy):
            with patch.object(tool, "_run_exploration", return_value=FakeTestResult()):
                result = await tool.execute(
                    endpoint_id="ep-1", strategy="domain_probing"
                )
                content = json.loads(result.content)
                assert "strategy_findings" in content
                assert content["strategy_findings"]["domain"] == "travel"


@pytest.mark.unit
class TestExploreEndpointToolComprehensive:
    """Test comprehensive mode (all strategies in sequence)."""

    def test_comprehensive_sequence_order(self):
        assert COMPREHENSIVE_STRATEGY_SEQUENCE == [
            "domain_probing",
            "capability_mapping",
            "boundary_discovery",
        ]

    @pytest.mark.asyncio
    async def test_comprehensive_runs_all_strategies(self):
        tool = ExploreEndpointTool(target_factory=lambda eid: FakeTarget(eid))

        strategies_called = []

        def mock_resolve(name):
            mock = MagicMock()
            mock.name = name
            mock.recommended_max_turns = 5
            mock.build_goal.return_value = f"Goal for {name}"
            mock.build_instructions.return_value = f"Instructions for {name}"
            mock.format_findings.return_value = {"strategy": name}
            strategies_called.append(name)
            return mock

        with patch.object(tool, "_resolve_strategy", side_effect=mock_resolve):
            with patch.object(tool, "_run_exploration", return_value=FakeTestResult()):
                result = await tool.execute(
                    endpoint_id="ep-1", strategy="comprehensive"
                )
                assert result.success
                content = json.loads(result.content)
                assert content["mode"] == "comprehensive"
                assert content["strategies_run"] == [
                    "domain_probing",
                    "capability_mapping",
                    "boundary_discovery",
                ]
                assert len(content["per_strategy_findings"]) == 3
                assert content["total_turns_used"] == 9  # 3 turns * 3 strategies

    @pytest.mark.asyncio
    async def test_comprehensive_chains_findings(self):
        """Domain probing findings feed into both parallel strategies.

        Capability mapping and boundary discovery run concurrently
        after domain probing, so they both see domain findings but
        neither sees the other's findings.
        """
        tool = ExploreEndpointTool(target_factory=lambda eid: FakeTarget(eid))
        build_goal_calls = {}

        def mock_resolve(name):
            mock = MagicMock()
            mock.name = name
            mock.recommended_max_turns = 5

            def capture_build_goal(**kwargs):
                pf = kwargs.get("previous_findings") or {}
                build_goal_calls[name] = dict(pf)
                return f"Goal for {name}"

            mock.build_goal.side_effect = capture_build_goal
            mock.build_instructions.return_value = f"Instructions for {name}"
            if name == "domain_probing":
                mock.format_findings.return_value = {
                    "strategy": name,
                    "domain": "travel",
                }
            elif name == "capability_mapping":
                mock.format_findings.return_value = {
                    "strategy": name,
                    "capabilities": ["booking"],
                }
            else:
                mock.format_findings.return_value = {
                    "strategy": name,
                    "refusal_patterns": ["off-topic"],
                }
            return mock

        with patch.object(tool, "_resolve_strategy", side_effect=mock_resolve):
            with patch.object(tool, "_run_exploration", return_value=FakeTestResult()):
                result = await tool.execute(
                    endpoint_id="ep-1", strategy="comprehensive"
                )
                assert result.success

                assert build_goal_calls["domain_probing"] == {}
                # Both parallel strategies receive domain probing findings
                assert build_goal_calls["capability_mapping"].get("domain") == "travel"
                assert build_goal_calls["boundary_discovery"].get("domain") == "travel"
                # Boundary discovery does NOT receive capability findings
                # (they run in parallel)
                assert "capabilities" not in build_goal_calls["boundary_discovery"]

    @pytest.mark.asyncio
    async def test_comprehensive_handles_strategy_failure(self):
        """If one strategy fails, comprehensive continues with the rest."""
        tool = ExploreEndpointTool(target_factory=lambda eid: FakeTarget(eid))

        def mock_resolve(name):
            mock = MagicMock()
            mock.name = name
            mock.recommended_max_turns = 5
            mock.build_goal.return_value = f"Goal for {name}"
            mock.build_instructions.return_value = f"Instructions for {name}"
            mock.format_findings.return_value = {"strategy": name}
            return mock

        def run_exploration_side_effect(**kwargs):
            goal = kwargs.get("goal", "")
            if "capability_mapping" in goal:
                raise RuntimeError("Penelope crashed")
            return FakeTestResult()

        with patch.object(tool, "_resolve_strategy", side_effect=mock_resolve):
            with patch.object(
                tool,
                "_run_exploration",
                side_effect=run_exploration_side_effect,
            ):
                result = await tool.execute(
                    endpoint_id="ep-1", strategy="comprehensive"
                )
                assert result.success
                content = json.loads(result.content)
                assert len(content["per_strategy_findings"]) == 3
                failed = [
                    f
                    for f in content["per_strategy_findings"]
                    if "error" in f
                ]
                assert len(failed) == 1


@pytest.mark.unit
class TestExploreEndpointToolHelpers:
    """Test helper methods."""

    def test_target_name_from_endpoint(self):
        class FakeEndpoint:
            id = "ep-1"
            name = "My Bot"
            description = "A cool bot"

        tool = ExploreEndpointTool(endpoint=FakeEndpoint())
        assert tool._target_name() == "My Bot"

    def test_target_name_fallback(self):
        tool = ExploreEndpointTool(target_factory=lambda eid: FakeTarget(eid))
        assert tool._target_name() == "endpoint"

    def test_target_description_from_endpoint(self):
        class FakeEndpoint:
            id = "ep-1"
            name = "My Bot"
            description = "A cool bot"

        tool = ExploreEndpointTool(endpoint=FakeEndpoint())
        assert tool._target_description() == "A cool bot"

    def test_target_description_fallback(self):
        tool = ExploreEndpointTool(target_factory=lambda eid: FakeTarget(eid))
        assert tool._target_description() == ""

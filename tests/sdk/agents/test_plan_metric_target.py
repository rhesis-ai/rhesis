"""Tests for a planned metric's target and save_plan's coverage validation."""

import pytest

from rhesis.sdk.agents.architect.plan import (
    ArchitectPlan,
    MappingSpec,
    MetricSpec,
    RequirementSpec,
    TestSetSpec,
    build_save_plan_tool,
)
from rhesis.sdk.metrics.targets import TargetKind


@pytest.mark.unit
class TestMetricTargetField:
    def test_defaults_to_each_turn(self):
        assert MetricSpec(name="Accuracy", description="d").target is TargetKind.TURN

    def test_rejects_an_unknown_target(self):
        with pytest.raises(ValueError, match="target"):
            MetricSpec(name="Accuracy", description="d", target="Single-Turn")

    @pytest.mark.parametrize(
        "scope, target",
        [
            (["Single-Turn"], TargetKind.TURN),
            (["Single-Turn", "Multi-Turn"], TargetKind.TURN),
            (["Multi-Turn"], TargetKind.CONVERSATION),
        ],
    )
    def test_an_old_plan_with_a_scope_still_loads(self, scope, target):
        metric = MetricSpec.model_validate(
            {"name": "Accuracy", "description": "d", "metric_scope": scope}
        )
        assert metric.target is target

    def test_save_plan_offers_every_target(self):
        schema = build_save_plan_tool()
        assert all(kind.value in str(schema) for kind in TargetKind)


@pytest.mark.unit
class TestMetricCoverage:
    def _plan(self, *, test_type: str = "Single-Turn", target: str = "turn") -> ArchitectPlan:
        return ArchitectPlan(
            requirements=[RequirementSpec(name="Refuses Harmful Requests", description="d")],
            test_sets=[
                TestSetSpec(
                    name="Guardrails",
                    description="d",
                    test_type=test_type,
                    requirements=["Refuses Harmful Requests"],
                )
            ],
            metrics=[MetricSpec(name="Safety Compliance", description="d", target=target)],
            requirement_metric_mappings=[
                MappingSpec(
                    requirement="Refuses Harmful Requests",
                    metrics=["Safety Compliance"],
                )
            ],
        )

    @pytest.mark.parametrize("test_type", ["Single-Turn", "Multi-Turn"])
    def test_a_turn_metric_judges_both_test_types(self, test_type):
        assert self._plan(test_type=test_type).test_sets[0].test_type == test_type

    def test_a_conversation_metric_judges_multi_turn_tests(self):
        plan = self._plan(test_type="Multi-Turn", target="conversation")
        assert plan.metrics[0].target is TargetKind.CONVERSATION

    def test_rejects_only_conversation_metrics_on_a_single_turn_test_set(self):
        with pytest.raises(ValueError, match="Metric coverage failed"):
            self._plan(test_type="Single-Turn", target="conversation")

    def test_a_per_span_metric_judges_single_turn_tests(self):
        assert self._plan(target="tool_call").metrics[0].target is TargetKind.TOOL_CALL

    def test_skips_coverage_when_test_set_has_no_requirements(self):
        plan = ArchitectPlan(
            requirements=[],
            test_sets=[TestSetSpec(name="Orphan", description="d", test_type="Single-Turn")],
            metrics=[MetricSpec(name="Safety Compliance", description="d", target="conversation")],
            requirement_metric_mappings=[],
        )
        assert plan.test_sets[0].requirements == []

    def test_rejects_a_requirement_without_mapping(self):
        with pytest.raises(ValueError, match="no requirement_metric_mappings"):
            ArchitectPlan(
                requirements=[RequirementSpec(name="Safety", description="d")],
                test_sets=[
                    TestSetSpec(
                        name="Tests",
                        description="d",
                        test_type="Single-Turn",
                        requirements=["Safety"],
                    )
                ],
                metrics=[MetricSpec(name="Accuracy", description="d")],
                requirement_metric_mappings=[],
            )

    def test_to_markdown_shows_the_target(self):
        assert (
            "judges: The conversation"
            in self._plan(test_type="Multi-Turn", target="conversation").to_markdown()
        )

"""Tests for metric_scope on ArchitectPlan and save_plan coverage validation."""

import pytest

from rhesis.sdk.agents.architect.plan import (
    ArchitectPlan,
    BehaviorSpec,
    MappingSpec,
    MetricSpec,
    TestSetSpec,
)


@pytest.mark.unit
class TestMetricScopeField:
    def test_rejects_invalid_scope_value(self):
        with pytest.raises(ValueError, match="metric_scope"):
            MetricSpec(
                name="Accuracy",
                description="d",
                metric_scope=["single-turn"],
            )

    def test_accepts_dual_scope(self):
        metric = MetricSpec(
            name="Domain Adherence",
            description="d",
            metric_scope=["Single-Turn", "Multi-Turn"],
        )
        assert metric.metric_scope == ["Single-Turn", "Multi-Turn"]


@pytest.mark.unit
class TestMetricScopeCoverage:
    def _plan(
        self,
        *,
        test_type: str = "Single-Turn",
        metric_scope: list[str] | None = None,
    ) -> ArchitectPlan:
        scope = metric_scope or ["Single-Turn"]
        return ArchitectPlan(
            behaviors=[BehaviorSpec(name="Refuses Harmful Requests", description="d")],
            test_sets=[
                TestSetSpec(
                    name="Guardrails",
                    description="d",
                    test_type=test_type,
                    behaviors=["Refuses Harmful Requests"],
                )
            ],
            metrics=[
                MetricSpec(
                    name="Safety Compliance",
                    description="d",
                    metric_scope=scope,
                )
            ],
            behavior_metric_mappings=[
                MappingSpec(
                    behavior="Refuses Harmful Requests",
                    metrics=["Safety Compliance"],
                )
            ],
        )

    def test_allows_matching_single_turn_scope(self):
        plan = self._plan()
        assert plan.metrics[0].metric_scope == ["Single-Turn"]

    def test_allows_matching_multi_turn_scope(self):
        plan = self._plan(test_type="Multi-Turn", metric_scope=["Multi-Turn"])
        assert plan.test_sets[0].test_type == "Multi-Turn"

    def test_rejects_single_turn_metric_on_multi_turn_test_set(self):
        with pytest.raises(ValueError, match="Metric scope coverage failed"):
            self._plan(test_type="Multi-Turn", metric_scope=["Single-Turn"])

    def test_rejects_multi_turn_metric_on_single_turn_test_set(self):
        with pytest.raises(ValueError, match="Metric scope coverage failed"):
            self._plan(test_type="Single-Turn", metric_scope=["Multi-Turn"])

    def test_dual_scope_satisfies_both_test_types(self):
        plan = self._plan(test_type="Multi-Turn", metric_scope=["Single-Turn", "Multi-Turn"])
        assert plan.test_sets[0].test_type == "Multi-Turn"

    def test_skips_coverage_when_test_set_has_no_behaviors(self):
        plan = ArchitectPlan(
            behaviors=[],
            test_sets=[TestSetSpec(name="Orphan", description="d", test_type="Multi-Turn")],
            metrics=[
                MetricSpec(
                    name="Safety Compliance",
                    description="d",
                    metric_scope=["Single-Turn"],
                )
            ],
            behavior_metric_mappings=[],
        )
        assert plan.test_sets[0].behaviors == []

    def test_rejects_behavior_without_mapping(self):
        with pytest.raises(ValueError, match="no behavior_metric_mappings"):
            ArchitectPlan(
                behaviors=[BehaviorSpec(name="Safety", description="d")],
                test_sets=[
                    TestSetSpec(
                        name="Tests",
                        description="d",
                        test_type="Single-Turn",
                        behaviors=["Safety"],
                    )
                ],
                metrics=[
                    MetricSpec(
                        name="Accuracy",
                        description="d",
                        metric_scope=["Single-Turn"],
                    )
                ],
                behavior_metric_mappings=[],
            )

    def test_to_markdown_shows_metric_scope(self):
        plan = self._plan()
        md = plan.to_markdown()
        assert "scope: Single-Turn" in md

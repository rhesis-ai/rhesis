"""Tests for a planned metric's target and save_plan's coverage validation."""

import pytest
from rhesis.telemetry.attributes import AIAttributes

from rhesis.sdk.agents.architect.plan import (
    ArchitectPlan,
    MappingSpec,
    MetricSpec,
    RequirementSpec,
    TestSetSpec,
    build_save_plan_tool,
)
from rhesis.sdk.agents.architect.plan_check import check_metric_shape
from rhesis.sdk.metrics.conditions import ConditionOp, SpecialField
from rhesis.sdk.metrics.targets import Aggregation, Reader, Target, TargetKind

_REFUND = {"on": TargetKind.TOOL_CALL.value, "name": "issue_refund", "within": "billing_agent"}
# The same spans as _REFUND, written as a span target with its conditions in another order.
_REFUND_AS_SPANS = {
    "on": TargetKind.SPAN.value,
    "where": [
        {"field": SpecialField.NAME.value, "op": ConditionOp.IN.value, "value": ["issue_refund"]},
        {
            "field": SpecialField.KIND.value,
            "op": ConditionOp.EQ.value,
            "value": AIAttributes.OPERATION_TOOL_INVOKE,
        },
    ],
    "within": "billing_agent",
}


@pytest.mark.unit
class TestMetricTargetField:
    def test_defaults_to_each_turn(self):
        assert MetricSpec(name="Accuracy", description="d").target.on is TargetKind.TURN

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
        assert metric.target.on is target

    def test_save_plan_offers_every_target(self):
        schema = build_save_plan_tool()
        assert all(kind.value in str(schema) for kind in TargetKind)

    def test_save_plan_takes_a_kind_or_a_full_target(self):
        metric = build_save_plan_tool()["parameters"]["properties"]["metrics"]["items"]
        short, full = metric["properties"]["target"]["anyOf"]

        assert short["enum"] == [kind.value for kind in TargetKind]
        assert {"on", "name", "within", "where", "read"} <= set(full["properties"])


@pytest.mark.unit
class TestMetricTargetForms:
    """A planned target loads from a bare kind, the older dict form or the full target, and is
    saved in the form the platform stores."""

    def test_a_bare_kind_loads(self):
        metric = MetricSpec(name="Refunds", description="d", target=TargetKind.TOOL_CALL.value)

        assert metric.target == Target(on=TargetKind.TOOL_CALL)

    def test_the_older_where_dict_loads_as_conditions(self):
        metric = MetricSpec(
            name="Refunds",
            description="d",
            target={"on": TargetKind.TOOL_CALL.value, "where": {"app.channel": ["email", "chat"]}},
        )

        (condition,) = metric.target.where
        assert (condition.field, condition.op) == ("app.channel", ConditionOp.IN)
        assert condition.value == ["email", "chat"]

    def test_a_full_span_target_loads(self):
        metric = MetricSpec(name="Refunds", description="d", target=_REFUND_AS_SPANS)

        assert metric.target.on is TargetKind.SPAN
        assert metric.target.within == "billing_agent"

    def test_a_target_this_sdk_cannot_read_is_refused(self):
        with pytest.raises(ValueError, match="not a target"):
            MetricSpec(name="Refunds", description="d", target={"on": "workflow"})

    def test_a_bare_kind_stays_a_kind_when_saved(self):
        # Plans saved before full targets hold the kind alone; they must save back unchanged.
        dumped = MetricSpec(name="Refunds", description="d", target="tool_call").model_dump()

        assert dumped["target"] == TargetKind.TOOL_CALL.value

    def test_a_narrowed_preset_is_saved_as_the_stored_form(self):
        dumped = MetricSpec(
            name="Refunds", description="d", target={"on": "tool_call", "name": "issue_refund"}
        ).model_dump(mode="json")

        assert dumped["target"] == {"on": TargetKind.TOOL_CALL.value, "name": "issue_refund"}

    def test_the_older_where_is_saved_as_a_list(self):
        metric = MetricSpec(
            name="Refunds",
            description="d",
            target={"on": TargetKind.TURN.value, "where": {"app.channel": "email"}},
        )

        assert metric.model_dump(mode="json")["target"]["where"] == [
            {"field": "app.channel", "op": ConditionOp.EQ.value, "value": "email"}
        ]

    @pytest.mark.parametrize(
        "target",
        [
            TargetKind.CONVERSATION.value,
            _REFUND,
            _REFUND_AS_SPANS,
            {
                **_REFUND,
                "read": {"input": Reader.CONVERSATION_INPUT.value},
                "aggregate": Aggregation.SHARE.value,
                "min_share": 0.9,
            },
        ],
    )
    def test_a_saved_plan_round_trips(self, target):
        plan = ArchitectPlan(metrics=[MetricSpec(name="Refunds", description="d", target=target)])

        stored = plan.model_dump(mode="json")
        reloaded = ArchitectPlan.model_validate(stored)

        assert reloaded.metrics[0].target == plan.metrics[0].target
        assert reloaded.model_dump(mode="json") == stored

    def test_a_plan_saved_with_a_bare_kind_still_loads(self):
        stored = {"metrics": [{"name": "Refunds", "description": "d", "target": "retrieval"}]}

        plan = ArchitectPlan.model_validate(stored)

        assert plan.metrics[0].target == Target(on=TargetKind.RETRIEVAL)

    def test_the_plan_shows_a_narrowed_target_in_words(self):
        plan = ArchitectPlan(metrics=[MetricSpec(name="Refunds", description="d", target=_REFUND)])

        assert "judges: each tool call named `issue_refund` inside `billing_agent`" in (
            plan.to_markdown()
        )


@pytest.mark.unit
class TestPlannedRules:
    def test_a_metric_is_a_judge_unless_a_rule_is_named(self):
        metric = MetricSpec(name="Accuracy", description="d")

        assert metric.rule is None
        assert metric.rule_settings == {}

    def test_a_rule_keeps_its_settings(self):
        metric = MetricSpec(
            name="Response Speed",
            description="d",
            rule="FieldRule",
            rule_settings={"field": "duration_ms", "op": "<=", "value": 5000},
        )

        assert metric.rule == "FieldRule"
        assert metric.rule_settings["value"] == 5000

    def test_an_unknown_rule_is_refused(self):
        with pytest.raises(ValueError, match="rule"):
            MetricSpec(name="Accuracy", description="d", rule="LatencyJudge")

    def test_save_plan_offers_every_rule(self):
        schema = str(build_save_plan_tool())

        for rule in ("FieldRule", "ResponseRule", "ToolCallTrajectory"):
            assert rule in schema

    @pytest.mark.parametrize(
        "rule, target",
        [
            ("ToolCallTrajectory", TargetKind.RUN),
            ("FieldRule", TargetKind.TURN),
            ("ResponseRule", TargetKind.TURN),
        ],
    )
    def test_a_rule_without_a_target_gets_its_class_default(self, rule, target):
        # The same default the server stores for that class.
        assert MetricSpec(name="Calls", description="d", rule=rule).target.on is target

    def test_a_chosen_target_is_kept(self):
        metric = MetricSpec(name="Calls", description="d", rule="ToolCallTrajectory", target="turn")

        assert metric.target.on is TargetKind.TURN


@pytest.mark.unit
class TestCreateCallTarget:
    """A create_metric call is checked against the planned target. Sending none means the
    server stores the class's own default."""

    @staticmethod
    def _plan(**metric) -> ArchitectPlan:
        return ArchitectPlan(metrics=[MetricSpec(name="Calls", description="d", **metric)])

    def test_no_target_matches_a_trajectory_planned_on_the_run(self):
        plan = self._plan(rule="ToolCallTrajectory")
        call = {"name": "Calls", "class_name": "ToolCallTrajectory"}

        assert check_metric_shape(plan, call) is None

    def test_no_target_is_not_each_turn_for_a_trajectory(self):
        plan = self._plan(rule="ToolCallTrajectory", target="turn")

        problem = check_metric_shape(plan, {"name": "Calls", "class_name": "ToolCallTrajectory"})

        assert problem is not None and "sends no target" in problem

    def test_no_target_on_a_custom_judge_is_each_turn(self):
        assert check_metric_shape(self._plan(), {"name": "Calls"}) is None

    @staticmethod
    def _create(target) -> dict:
        return {"name": "Calls", "config": {"target": target}}

    @pytest.mark.parametrize(
        "planned, sent",
        [
            (_REFUND, _REFUND_AS_SPANS),
            (_REFUND_AS_SPANS, _REFUND),
            (TargetKind.TOOL_CALL.value, {"on": TargetKind.TOOL_CALL.value}),
            (TargetKind.TOOL_CALL.value, TargetKind.TOOL_CALL.value),
        ],
    )
    def test_a_preset_and_its_span_form_are_the_same_target(self, planned, sent):
        assert check_metric_shape(self._plan(target=planned), self._create(sent)) is None

    def test_the_order_of_values_in_a_choice_does_not_matter(self):
        def target(values):
            return {
                "on": TargetKind.SPAN.value,
                "where": [{"field": "app.tier", "op": ConditionOp.IN.value, "value": values}],
            }

        plan = self._plan(target=target(["gold", "silver"]))

        assert check_metric_shape(plan, self._create(target(["silver", "gold"]))) is None

    def test_a_dropped_condition_is_flagged_in_words(self):
        plan = self._plan(
            target={**_REFUND, "where": [("app.channel", ConditionOp.NE.value, "internal")]}
        )

        problem = check_metric_shape(plan, self._create(_REFUND))

        assert problem is not None
        assert "where `app.channel` is not `internal`" in problem
        assert "each tool call named `issue_refund` inside `billing_agent`." in problem

    def test_a_different_within_is_flagged(self):
        problem = check_metric_shape(
            self._plan(target=_REFUND), self._create({**_REFUND, "within": "support_agent"})
        )

        assert problem is not None and "inside `support_agent`" in problem

    def test_a_different_read_is_named(self):
        sent = {**_REFUND, "read": {"input": Reader.CONVERSATION_INPUT.value}}

        problem = check_metric_shape(self._plan(target=_REFUND), self._create(sent))

        assert problem is not None and "differ in what the metric reads" in problem

    def test_a_different_pass_rule_is_named(self):
        sent = {**_REFUND, "aggregate": Aggregation.ANY.value}

        problem = check_metric_shape(self._plan(target=_REFUND), self._create(sent))

        assert problem is not None and "how the verdicts combine" in problem

    def test_the_fix_sends_the_planned_target(self):
        problem = check_metric_shape(
            self._plan(target=_REFUND), self._create(TargetKind.TOOL_CALL.value)
        )

        assert problem is not None
        assert '"name": "issue_refund"' in problem and '"within": "billing_agent"' in problem

    def test_a_target_the_server_would_refuse_is_left_to_the_server(self):
        plan = self._plan(target=_REFUND)

        assert check_metric_shape(plan, self._create({"on": TargetKind.SPAN.value})) is None


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
        assert plan.metrics[0].target.on is TargetKind.CONVERSATION

    def test_rejects_only_conversation_metrics_on_a_single_turn_test_set(self):
        with pytest.raises(ValueError, match="Metric coverage failed"):
            self._plan(test_type="Single-Turn", target="conversation")

    def test_a_per_span_metric_judges_single_turn_tests(self):
        assert self._plan(target="tool_call").metrics[0].target.on is TargetKind.TOOL_CALL

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

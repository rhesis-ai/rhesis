"""The plan has to describe what actually got built.

Issue #2785: a run asked for 95 tests, 8 were created, and the summary said
95. Two different faults produce that, and each is covered here.

A *substitution* is a call whose arguments contradict the plan. The name
guard on create_metric was the only one of these in place; the rest of the
plan's fields were advice in a tool description. These tests pin the guards
that make the plan binding.

A *shortfall* is a set that ends up smaller than planned. Every call
succeeds, so nothing anywhere says it fell short -- the plan item is marked
complete and the ratio reads N/N. These tests pin the counting that makes the
gap visible in the prompts the model writes its summary from.
"""

import json

import pytest

from rhesis.sdk.agents.architect.plan import (
    ArchitectPlan,
    MappingSpec,
    MetricSpec,
    RequirementSpec,
    TestSetSpec,
)
from rhesis.sdk.agents.architect.state import ArchitectAgentStateSnapshot
from rhesis.sdk.agents.schemas import ToolCall, ToolResult
from tests.sdk.agents.test_architect import _make_agent, _mock_model


def _plan(**overrides) -> ArchitectPlan:
    """A minimal coherent plan: one requirement, one metric, one mapped set."""
    base = {
        "requirements": [RequirementSpec(name="Refuses Harmful Requests")],
        "metrics": [
            MetricSpec(
                name="Safety Compliance",
                description="Scores refusal quality",
                metric_scope=["Single-Turn"],
            )
        ],
        "test_sets": [
            TestSetSpec(
                name="Guardrails",
                description="Safety guardrail tests",
                num_tests=40,
                requirements=["Refuses Harmful Requests"],
            )
        ],
        "requirement_metric_mappings": [
            MappingSpec(requirement="Refuses Harmful Requests", metrics=["Safety Compliance"])
        ],
    }
    base.update(overrides)
    return ArchitectPlan(**base)


def _agent(plan=None):
    agent = _make_agent(_mock_model())
    agent._plan = plan if plan is not None else _plan()
    return agent


def _call(tool_name, **arguments) -> ToolCall:
    return ToolCall(tool_name=tool_name, arguments=json.dumps(arguments))


def _ok(tool_name, payload) -> ToolResult:
    return ToolResult(tool_name=tool_name, success=True, content=json.dumps(payload))


# ── substitution: the name has to be one the plan named ──────────


@pytest.mark.unit
class TestOnlyPlannedThingsGetCreated:
    """An entity created under an unplanned name is work nobody approved.

    It also never marks its plan item done, because every progress tracker
    matches on name -- so the plan reads incomplete while the platform fills
    up with things the plan does not describe.
    """

    def test_an_unplanned_requirement_is_refused(self):
        error = _agent()._check_plan_constraints(_call("create_requirement", name="Invented"))

        assert error is not None
        assert "does not match" in error
        assert "Refuses Harmful Requests" in error

    def test_an_unplanned_test_set_is_refused(self):
        error = _agent()._check_plan_constraints(_call("create_test_set_bulk", name="Invented"))

        assert error is not None
        assert "does not match" in error
        assert "Guardrails" in error

    def test_the_planned_name_is_accepted(self):
        error = _agent()._check_plan_constraints(
            _call("create_requirement", name="Refuses Harmful Requests")
        )

        assert error is None

    def test_matching_is_case_insensitive(self):
        """The plan's own trackers match case-insensitively; so must the guard,
        or a capitalisation difference reads as an invented name."""
        error = _agent()._check_plan_constraints(
            _call("create_requirement", name="refuses harmful requests")
        )

        assert error is None

    def test_a_requirement_named_only_in_a_mapping_is_accepted(self):
        """The plan validator does not make a mapping's requirement appear in
        plan.requirements, so a plan can legitimately name one there alone.
        Refusing it would block work the plan does call for."""
        plan = _plan(
            requirements=[],
            test_sets=[],
            requirement_metric_mappings=[
                MappingSpec(requirement="Stays On Topic", metrics=["Safety Compliance"])
            ],
        )

        error = _agent(plan)._check_plan_constraints(
            _call("create_requirement", name="Stays On Topic")
        )

        assert error is None

    def test_a_requirement_named_only_by_a_test_set_is_accepted(self):
        plan = _plan(requirements=[])

        error = _agent(plan)._check_plan_constraints(
            _call("create_requirement", name="Refuses Harmful Requests")
        )

        assert error is None

    def test_a_metric_named_only_in_a_mapping_is_accepted(self):
        plan = _plan(metrics=[], test_sets=[])

        error = _agent(plan)._check_plan_constraints(
            _call("create_metric", name="Safety Compliance")
        )

        assert error is None

    def test_an_unplanned_metric_is_still_refused(self):
        """The one guard that already existed keeps behaving the same way."""
        error = _agent()._check_plan_constraints(_call("create_metric", name="Coherence"))

        assert error is not None
        assert "does not match" in error
        assert "Safety Compliance" in error

    def test_a_call_without_a_name_is_left_alone(self):
        """add_requirement_to_metric and friends pass ids, not names."""
        error = _agent()._check_plan_constraints(
            _call("add_requirement_to_metric", metric_id="m-1", requirement_id="b-1")
        )

        assert error is None

    def test_nothing_is_checked_without_a_plan(self):
        agent = _make_agent(_mock_model())
        agent._plan = None

        assert agent._check_plan_constraints(_call("create_metric", name="Anything")) is None


# ── substitution: the settings have to be the planned ones ───────


@pytest.mark.unit
class TestThingsGetBuiltInTheShapeThatWasPlanned:
    """A matching name is not a matching thing.

    A metric only runs against test types in its scope, so a set generated in
    the other shape is evaluated by nothing at all -- and that surfaces as an
    empty result, not as an error.
    """

    def test_a_set_planned_multi_turn_cannot_be_generated_single_turn(self):
        plan = _plan(
            test_sets=[
                TestSetSpec(name="Pressure", description="d", test_type="Multi-Turn", num_tests=10)
            ]
        )

        error = _agent(plan)._check_plan_constraints(
            _call("generate_test_set", name="Pressure", test_type="Single-Turn")
        )

        assert error is not None
        assert "Multi-Turn" in error

    def test_the_bulk_writer_spells_the_argument_differently(self):
        """generate_test_set sends test_type, create_test_set_bulk sends
        test_set_type. Checking only one of them leaves the other open."""
        plan = _plan(
            test_sets=[
                TestSetSpec(name="Pressure", description="d", test_type="Multi-Turn", num_tests=10)
            ]
        )

        error = _agent(plan)._check_plan_constraints(
            _call("create_test_set_bulk", name="Pressure", test_set_type="Single-Turn")
        )

        assert error is not None
        assert "Multi-Turn" in error

    def test_the_planned_shape_is_accepted(self):
        """Prerequisites are completed here so the pre-existing ordering guard
        does not answer first and hide what this test is about."""
        plan = _plan(
            requirements=[RequirementSpec(name="Refuses Harmful Requests", completed=True)],
            metrics=[
                MetricSpec(
                    name="Safety Compliance",
                    description="Scores refusal quality",
                    metric_scope=["Single-Turn"],
                    completed=True,
                )
            ],
            requirement_metric_mappings=[
                MappingSpec(
                    requirement="Refuses Harmful Requests",
                    metrics=["Safety Compliance"],
                    completed=True,
                )
            ],
        )

        error = _agent(plan)._check_plan_constraints(
            _call("generate_test_set", name="Guardrails", test_type="Single-Turn")
        )

        assert error is None

    def test_a_metric_scope_that_differs_is_refused(self):
        error = _agent()._check_plan_constraints(
            _call("create_metric", name="Safety Compliance", metric_scope=["Multi-Turn"])
        )

        assert error is not None
        assert "metric_scope" in error

    def test_a_threshold_that_differs_is_refused(self):
        error = _agent()._check_plan_constraints(
            _call("create_metric", name="Safety Compliance", threshold=0.5)
        )

        assert error is not None
        assert "threshold" in error

    def test_a_threshold_operator_that_differs_is_refused(self):
        error = _agent()._check_plan_constraints(
            _call("create_metric", name="Safety Compliance", threshold_operator="<")
        )

        assert error is not None
        assert "threshold_operator" in error

    def test_fields_the_call_omits_are_not_compared(self):
        """Every plan field has a default. Comparing one the call never sent
        would fire on ordinary work until nobody read the warnings any more --
        so absence means "not stated", not "mismatched"."""
        error = _agent()._check_plan_constraints(_call("create_metric", name="Safety Compliance"))

        assert error is None

    def test_an_unplanned_set_is_not_shape_checked(self):
        """The name guard owns that case; reporting both at once is noise."""
        plan = _plan(test_sets=[])

        error = _agent(plan)._check_plan_constraints(
            _call("generate_test_set", name="Guardrails", test_type="Multi-Turn")
        )

        assert "test_type" not in (error or "")


# ── shortfall: the plan has to show what was really written ──────


@pytest.mark.unit
class TestASetThatLandsShortSaysSo:
    """Issue #2785's own failure: 95 asked for, 8 written, 95 reported.

    Every call succeeded. count_check catches a batch smaller than the batch
    sent, but not a plan of 40 satisfied by sending 12 -- there the request
    and the response agree, and only the plan disagrees.
    """

    def _wrote(self, agent, name, count, test_set_id="ts-1"):
        agent._record_tests_written(
            _call("create_test_set_bulk", name=name),
            _ok("create_test_set_bulk", {"id": test_set_id, "name": name, "total_tests": count}),
        )

    def test_a_short_set_is_marked_short_on_the_plan(self):
        agent = _agent()

        self._wrote(agent, "Guardrails", 12)

        assert agent._plan.test_sets[0].actual_tests == 12
        assert agent._plan.test_sets[0].shortfall() == 28

    def test_the_shortfall_is_stated_in_the_plan_the_prompts_render(self):
        """Both the iteration prompt and the streaming prompt that writes the
        final answer render the plan markdown, and only that one. A warning
        anywhere else never reaches the summary."""
        agent = _agent()

        self._wrote(agent, "Guardrails", 12)
        markdown = agent._plan.to_markdown()

        assert "WROTE 12 OF 40" in markdown
        assert "do not report 40 tests" in markdown.lower()

    def test_the_shortfall_is_stated_in_the_progress_line(self):
        agent = _agent()

        self._wrote(agent, "Guardrails", 12)

        assert "Short of plan" in agent._format_plan_progress()
        assert "12 of 40" in agent._format_plan_progress()

    def test_batches_add_up(self):
        """A large set is built by create_test_set_bulk then add_tests_bulk per
        batch. Counting only the first call would report every such set short."""
        agent = _agent()

        self._wrote(agent, "Guardrails", 25)
        for _ in range(2):
            agent._record_tests_written(
                _call("add_tests_bulk", test_set_id="ts-1"),
                _ok("add_tests_bulk", {"success": True, "total_tests": 5}),
            )

        assert agent._plan.test_sets[0].actual_tests == 35
        assert agent._plan.test_sets[0].shortfall() == 5

    def test_reaching_the_plan_reports_nothing(self):
        agent = _agent()

        self._wrote(agent, "Guardrails", 40)

        assert agent._plan.test_sets[0].shortfall() is None
        assert "Short of plan" not in agent._format_plan_progress()
        assert "WROTE" not in agent._plan.to_markdown()

    def test_an_overshoot_reports_nothing(self):
        """Extra tests are someone adding them on purpose, not a fault."""
        agent = _agent()

        self._wrote(agent, "Guardrails", 45)

        assert agent._plan.test_sets[0].shortfall() is None

    def test_an_unattempted_set_is_not_called_short(self):
        agent = _agent()

        assert agent._plan.test_sets[0].shortfall() is None
        assert "Short of plan" not in agent._format_plan_progress()

    def test_a_batch_for_an_unknown_set_is_ignored(self):
        """add_tests_bulk carries only an id. Crediting it to the wrong set
        would be worse than not counting it."""
        agent = _agent()

        agent._record_tests_written(
            _call("add_tests_bulk", test_set_id="never-seen"),
            _ok("add_tests_bulk", {"success": True, "total_tests": 5}),
        )

        assert agent._plan.test_sets[0].actual_tests is None

    def test_a_response_without_a_count_is_not_read_as_zero(self):
        """Recording zero would invent a shortfall that did not happen."""
        agent = _agent()

        agent._record_tests_written(
            _call("create_test_set_bulk", name="Guardrails"),
            _ok("create_test_set_bulk", {"id": "ts-1", "name": "Guardrails"}),
        )

        assert agent._plan.test_sets[0].actual_tests is None

    def test_a_non_json_response_does_not_raise(self):
        agent = _agent()

        agent._record_tests_written(
            _call("create_test_set_bulk", name="Guardrails"),
            ToolResult(tool_name="create_test_set_bulk", success=True, content="not json"),
        )

        assert agent._plan.test_sets[0].actual_tests is None


@pytest.mark.unit
class TestGeneratedSetsAreCountedToo:
    """generate_test_set runs as a job, so its count arrives in the
    [TASK_COMPLETED] message rather than in a tool result."""

    @pytest.mark.asyncio
    async def test_the_generated_count_is_taken_from_the_message(self):
        agent = _agent()

        await agent._apply_task_completions(
            "[TASK_COMPLETED] Test set 'Guardrails' generated successfully "
            "(12 tests). test_set_id=ts-1"
        )

        assert agent._plan.test_sets[0].actual_tests == 12
        assert agent._plan.test_sets[0].shortfall() == 28

    @pytest.mark.asyncio
    async def test_a_short_generated_set_can_be_topped_up(self):
        """The whole point of reporting a shortfall is that it can be fixed.

        Topping up calls add_tests_bulk, which carries only the set id, so the
        id has to be taken from the completion message too. Without it the
        top-up is credited to nothing and the set reads short forever -- worse
        than not counting, because the agent is told to fix what it just did.
        """
        agent = _agent()
        await agent._apply_task_completions(
            "[TASK_COMPLETED] Test set 'Guardrails' generated successfully "
            "(12 tests). test_set_id=ts-9"
        )
        assert agent._plan.test_sets[0].shortfall() == 28

        agent._record_tests_written(
            _call("add_tests_bulk", test_set_id="ts-9"),
            _ok("add_tests_bulk", {"success": True, "total_tests": 28}),
        )

        assert agent._plan.test_sets[0].actual_tests == 40
        assert agent._plan.test_sets[0].shortfall() is None
        assert "Short of plan" not in agent._format_plan_progress()

    @pytest.mark.asyncio
    async def test_an_unknown_count_still_completes_the_item(self):
        """The monitor writes "?" when the job result carried no count. The
        completion must still register, and no shortfall be invented."""
        agent = _agent()

        await agent._apply_task_completions(
            "[TASK_COMPLETED] Test set 'Guardrails' generated successfully "
            "(? tests). test_set_id=ts-1"
        )

        assert agent._plan.test_sets[0].completed is True
        assert agent._plan.test_sets[0].actual_tests is None

    @pytest.mark.asyncio
    async def test_an_unknown_count_does_not_become_a_wrong_one(self):
        """A top-up after an unknown count must not be read as the whole set.

        The id is deliberately not kept when the count is missing. Keeping it
        would let the next batch start a running total from zero, so a set the
        generator had already filled would report only the top-up and claim a
        shortfall of everything written before it. Saying nothing about the
        size is honest; saying 28 of 40 for a full set is not.
        """
        agent = _agent()
        await agent._apply_task_completions(
            "[TASK_COMPLETED] Test set 'Guardrails' generated successfully "
            "(? tests). test_set_id=ts-9"
        )

        agent._record_tests_written(
            _call("add_tests_bulk", test_set_id="ts-9"),
            _ok("add_tests_bulk", {"success": True, "total_tests": 28}),
        )

        assert agent._plan.test_sets[0].actual_tests is None
        assert agent._plan.test_sets[0].shortfall() is None
        assert "Short of plan" not in agent._format_plan_progress()


@pytest.mark.unit
class TestTheCountsOutliveThePlanBeingResaved:
    """``actual_tests`` is internal, so save_plan strips it and the LLM's
    payload restores the default. The counts are kept beside the plan and
    written back, the same way ``completed`` is."""

    def test_a_resaved_plan_keeps_the_counts(self):
        agent = _agent()
        agent._record_tests_written(
            _call("create_test_set_bulk", name="Guardrails"),
            _ok("create_test_set_bulk", {"id": "ts-1", "total_tests": 12}),
        )

        # What save_plan does: a fresh plan built from the LLM's payload.
        agent._plan = _plan()
        assert agent._plan.test_sets[0].actual_tests is None

        agent._reconcile_plan_with_session_evidence(agent._plan)

        assert agent._plan.test_sets[0].actual_tests == 12

    def test_the_counts_survive_a_state_round_trip(self):
        """A set is often filled across turns, and each turn is a new agent
        rebuilt from the snapshot."""
        agent = _agent()
        agent._record_tests_written(
            _call("create_test_set_bulk", name="Guardrails"),
            _ok("create_test_set_bulk", {"id": "ts-1", "total_tests": 12}),
        )

        restored = _make_agent(_mock_model())
        restored.restore_state(agent.dump_state())

        assert restored._plan.test_sets[0].actual_tests == 12
        assert restored._test_set_names_by_id == {"ts-1": "Guardrails"}

    def test_a_later_batch_finds_its_set_after_a_turn_boundary(self):
        agent = _agent()
        agent._record_tests_written(
            _call("create_test_set_bulk", name="Guardrails"),
            _ok("create_test_set_bulk", {"id": "ts-1", "total_tests": 25}),
        )

        restored = _make_agent(_mock_model())
        restored.restore_state(agent.dump_state())
        restored._record_tests_written(
            _call("add_tests_bulk", test_set_id="ts-1"),
            _ok("add_tests_bulk", {"success": True, "total_tests": 15}),
        )

        assert restored._plan.test_sets[0].actual_tests == 40
        assert restored._plan.test_sets[0].shortfall() is None

    def test_a_plan_stored_before_this_field_existed_still_loads(self):
        agent = _make_agent(_mock_model())

        agent.restore_state(
            ArchitectAgentStateSnapshot(
                mode="planning",
                plan_data={
                    "test_sets": [{"name": "Guardrails", "description": "d", "num_tests": 40}],
                },
            )
        )

        assert agent._plan.test_sets[0].actual_tests is None

"""Tests for Penelope utils module."""

from datetime import datetime, timedelta
from unittest.mock import Mock

import pytest
from helpers import add_turns_to_state

from rhesis.penelope.context import ExecutionStatus
from rhesis.penelope.utils import (
    GoalAchievedCondition,
    MaxTurnsCondition,
    StoppingCondition,
    StopResult,
    TimeoutCondition,
)


def test_stopping_condition_base_class():
    """Test that StoppingCondition base class exists."""
    assert hasattr(StoppingCondition, "should_stop")


def test_stopping_condition_not_implemented():
    """Test that StoppingCondition.should_stop is not implemented."""
    condition = StoppingCondition()

    with pytest.raises(NotImplementedError):
        condition.should_stop(None)


def test_max_turns_condition_initialization():
    """Test MaxTurnsCondition initialization."""
    condition = MaxTurnsCondition(max_turns=10)

    assert condition.max_turns == 10


def test_max_turns_condition_should_not_stop(sample_test_state):
    """Test MaxTurnsCondition doesn't stop before limit."""
    condition = MaxTurnsCondition(max_turns=10)

    result = condition.should_stop(sample_test_state)

    assert result.should_stop is False
    assert result.status is None
    assert result.reason == ""


def test_max_turns_condition_should_stop(sample_test_state):
    """Test MaxTurnsCondition stops at limit."""
    condition = MaxTurnsCondition(max_turns=5)

    # Simulate reaching max turns
    for _ in range(5):
        sample_test_state.current_turn += 1

    result = condition.should_stop(sample_test_state)

    assert result.should_stop is True
    assert result.status == ExecutionStatus.MAX_TURNS
    assert "Maximum turns" in result.reason
    assert "5" in result.reason


def test_timeout_condition_initialization():
    """Test TimeoutCondition initialization."""
    condition = TimeoutCondition(timeout_seconds=60.0)

    assert condition.timeout_seconds == 60.0


def test_timeout_condition_should_not_stop(sample_test_state):
    """Test TimeoutCondition doesn't stop before timeout."""
    condition = TimeoutCondition(timeout_seconds=60.0)

    result = condition.should_stop(sample_test_state)

    assert result.should_stop is False
    assert result.status is None


def test_timeout_condition_should_stop(sample_test_state):
    """Test TimeoutCondition stops after timeout."""
    condition = TimeoutCondition(timeout_seconds=1.0)

    # Simulate time passing
    sample_test_state.start_time = datetime.now() - timedelta(seconds=2)

    result = condition.should_stop(sample_test_state)

    assert result.should_stop is True
    assert result.status == ExecutionStatus.TIMEOUT
    assert "Timeout" in result.reason


def test_goal_achieved_condition_initialization():
    """Test GoalAchievedCondition initialization."""
    mock_result = Mock()
    mock_result.score = 0.5
    mock_result.details = {"is_successful": False, "reason": "Testing"}

    condition = GoalAchievedCondition(result=mock_result)

    assert condition.result == mock_result


def test_goal_achieved_condition_initialization_without_result():
    """Test GoalAchievedCondition can be initialized without result."""
    condition = GoalAchievedCondition()

    assert condition.result is None


def test_goal_achieved_condition_should_not_stop_no_result(sample_test_state):
    """Test GoalAchievedCondition doesn't stop without result."""
    condition = GoalAchievedCondition()

    result = condition.should_stop(sample_test_state)

    assert result.should_stop is False
    assert result.status is None


def test_goal_achieved_condition_should_not_stop_goal_not_achieved(
    sample_test_state,
):
    """Test GoalAchievedCondition doesn't stop if goal not achieved."""
    mock_result = Mock()
    mock_result.score = 0.5
    mock_result.details = {"is_successful": False, "reason": "Still working"}

    condition = GoalAchievedCondition(result=mock_result)

    result = condition.should_stop(sample_test_state)

    assert result.should_stop is False
    assert result.status is None


def test_goal_achieved_condition_should_stop_goal_achieved(sample_test_state):
    """Test GoalAchievedCondition stops when goal achieved."""
    mock_result = Mock()
    mock_result.score = 0.9
    mock_result.details = {
        "is_successful": True,
        "reason": "Goal successfully achieved",
    }

    condition = GoalAchievedCondition(result=mock_result)

    result = condition.should_stop(sample_test_state)

    assert result.should_stop is True
    assert result.status == ExecutionStatus.SUCCESS
    assert "Goal achieved" in result.reason
    assert "successfully achieved" in result.reason


def test_goal_achieved_condition_should_stop_goal_impossible(
    sample_test_state,
):
    """Test GoalAchievedCondition stops when goal is impossible."""
    mock_result = Mock()
    mock_result.score = 0.2
    mock_result.details = {
        "is_successful": False,
        "reason": "Cannot achieve goal",
    }

    condition = GoalAchievedCondition(result=mock_result)
    add_turns_to_state(sample_test_state, 5)

    result = condition.should_stop(sample_test_state)

    assert result.should_stop is True
    assert result.status == ExecutionStatus.FAILURE
    assert "impossible" in result.reason.lower()


def test_goal_achieved_condition_update_result():
    """Test GoalAchievedCondition can update result."""
    condition = GoalAchievedCondition()

    assert condition.result is None

    mock_result = Mock()
    mock_result.score = 0.9
    mock_result.details = {"is_successful": True, "reason": "Updated"}

    condition.update_result(mock_result)

    assert condition.result == mock_result


class TestGoalAchievedConditionContractMode:
    """Contract-based results (marked by ``behaviors_total`` in details, see
    ``GoalAchievementJudge.is_contract_result``) use a different stopping rule: compliance so
    far must never be read as final, because nothing has necessarily tried to break it yet.
    """

    @staticmethod
    def _verdict(kind: str, complied: bool, behavior: str = "Some behaviour") -> dict:
        return {"behavior": behavior, "kind": kind, "complied": complied, "evidence": ""}

    @classmethod
    def _contract_result(cls, is_successful: bool, verdicts=None, **extra_details) -> Mock:
        """A contract-shaped result. ``verdicts`` defaults to matching ``is_successful`` via a
        single prohibited behaviour, which is the case that legitimately stops a run.
        """
        if verdicts is None:
            verdicts = [cls._verdict("prohibited", complied=is_successful)]
        result = Mock()
        result.score = 1.0 if is_successful else 0.0
        result.details = {
            "behaviors_total": len(verdicts),
            "behavior_verdicts": verdicts,
            "is_successful": is_successful,
            "reason": "Contract reason",
            **extra_details,
        }
        return result

    def test_does_not_stop_on_compliance_no_matter_how_many_turns(self, sample_test_state):
        """The bug this design exists to prevent: stopping on 'nothing violated yet'."""
        condition = GoalAchievedCondition(result=self._contract_result(True))
        add_turns_to_state(sample_test_state, 9)  # far past any goal-based floor

        result = condition.should_stop(sample_test_state)

        assert result.should_stop is False

    def test_does_not_stop_on_compliance_even_at_turn_one(self, sample_test_state):
        """No floor gating for contract mode -- there is nothing to gate against."""
        condition = GoalAchievedCondition(result=self._contract_result(True))

        result = condition.should_stop(sample_test_state)

        assert result.should_stop is False

    def test_stops_on_a_violated_prohibition(self, sample_test_state):
        condition = GoalAchievedCondition(
            result=self._contract_result(
                False,
                verdicts=[self._verdict("prohibited", False, "Disclose PII")],
            )
        )
        add_turns_to_state(sample_test_state, 1)

        result = condition.should_stop(sample_test_state)

        assert result.should_stop is True
        assert result.status == ExecutionStatus.FAILURE
        assert result.goal_achieved is False
        assert "Contract reason" in result.reason

    def test_stops_on_a_violated_prohibition_at_turn_one_with_no_floor(self, sample_test_state):
        """A breached prohibition is permanent, so there is no reason to wait for a turn floor."""
        condition = GoalAchievedCondition(
            result=self._contract_result(False), min_turns=8, max_turns=10
        )

        result = condition.should_stop(sample_test_state)

        assert result.should_stop is True

    def test_does_not_stop_on_a_required_behaviour_not_yet_done(self, sample_test_state):
        """A required behaviour that hasn't happened yet is not a violation, it's just not done.

        The judge marks a required behaviour non-compliant when the system "never got the
        chance", and it first runs at ``min_turns``. Stopping there would end the run before the
        scenario it is waiting for could occur, and report Fail for a test that never ran.
        """
        condition = GoalAchievedCondition(
            result=self._contract_result(
                False,
                verdicts=[self._verdict("required", False, "Escalate to a human operator")],
            ),
            min_turns=1,
            max_turns=10,
        )
        add_turns_to_state(sample_test_state, 1)

        result = condition.should_stop(sample_test_state)

        assert result.should_stop is False

    def test_stops_on_a_prohibition_even_alongside_a_pending_requirement(self, sample_test_state):
        """A real breach still stops, even when a requirement is also outstanding."""
        condition = GoalAchievedCondition(
            result=self._contract_result(
                False,
                verdicts=[
                    self._verdict("required", False, "Escalate to a human operator"),
                    self._verdict("prohibited", False, "Disclose PII"),
                ],
            )
        )
        add_turns_to_state(sample_test_state, 2)

        result = condition.should_stop(sample_test_state)

        assert result.should_stop is True
        assert result.status == ExecutionStatus.FAILURE

    def test_does_not_stop_when_the_judge_itself_errored(self, sample_test_state):
        """An errored judge is contract-shaped but carries no verdicts.

        ``behaviors_total`` is stamped before the model call and ``handle_evaluation_error`` sets
        ``is_successful=False``, so an error looks like a failed contract run. Reading it as a
        breach would turn a transient model timeout into a recorded security failure.
        """
        condition = GoalAchievedCondition(
            result=self._contract_result(
                False,
                verdicts=[],
                error="Error evaluating with Goal Achievement: timeout",
            )
        )
        add_turns_to_state(sample_test_state, 5)

        result = condition.should_stop(sample_test_state)

        assert result.should_stop is False

    def test_a_low_score_alone_does_not_stop_when_compliant(self, sample_test_state):
        """Contract mode has no 'impossible score' branch -- only a breached prohibition stops."""
        result_mock = self._contract_result(True)
        result_mock.score = 0.05  # low score, but nothing was violated
        condition = GoalAchievedCondition(result=result_mock, impossible_score_threshold=0.3)
        add_turns_to_state(sample_test_state, 9)

        result = condition.should_stop(sample_test_state)

        assert result.should_stop is False

    def test_goal_based_result_is_unaffected(self, sample_test_state):
        """A result with no behaviors_total key must take the legacy goal-based path."""
        mock_result = Mock()
        mock_result.score = 0.9
        mock_result.details = {"is_successful": True, "reason": "Goal achieved"}
        condition = GoalAchievedCondition(result=mock_result)
        add_turns_to_state(sample_test_state, 9)

        result = condition.should_stop(sample_test_state)

        assert result.should_stop is True
        assert result.status == ExecutionStatus.SUCCESS


def test_min_turns_blocks_early_stop(sample_test_state):
    """Test that min_turns prevents early stopping."""
    mock_result = Mock()
    mock_result.score = 0.9
    mock_result.details = {
        "is_successful": True,
        "reason": "Goal achieved",
    }

    condition = GoalAchievedCondition(result=mock_result, max_turns=10, min_turns=8)
    add_turns_to_state(sample_test_state, 5)

    # At 5 turns with min_turns=8, should NOT stop
    result = condition.should_stop(sample_test_state)
    assert result.should_stop is False


def test_min_turns_allows_stop_after_threshold(sample_test_state):
    """Test that early stopping is allowed after min_turns is reached."""
    mock_result = Mock()
    mock_result.score = 0.9
    mock_result.details = {
        "is_successful": True,
        "reason": "Goal achieved",
    }

    condition = GoalAchievedCondition(result=mock_result, max_turns=10, min_turns=5)
    add_turns_to_state(sample_test_state, 5)

    # At 5 turns with min_turns=5, should stop
    result = condition.should_stop(sample_test_state)
    assert result.should_stop is True
    assert result.status == ExecutionStatus.SUCCESS
    assert "Goal achieved" in result.reason


def test_min_turns_capped_at_max_turns(sample_test_state):
    """Test that min_turns cannot exceed max_turns."""
    condition = GoalAchievedCondition(max_turns=10, min_turns=15)

    # min_turns=15 should be capped to max_turns=10
    assert condition._get_early_stop_floor(strict=False) == 10


def test_default_threshold_when_no_min_turns():
    """Test that 80% threshold applies when min_turns is not set."""
    condition = GoalAchievedCondition(max_turns=10)

    # 80% of 10 = 8
    assert condition._get_early_stop_floor(strict=False) == 8


def test_no_floor_when_neither_set():
    """Test fallback to 0 when neither max_turns nor min_turns is set."""
    condition = GoalAchievedCondition()

    assert condition._get_early_stop_floor(strict=False) == 0


def test_stop_result_continue():
    """Test StopResult.continue_() sentinel."""
    result = StopResult.continue_()

    assert result.should_stop is False
    assert result.status is None
    assert result.reason == ""


def test_stop_result_with_status():
    """Test StopResult with a status."""
    result = StopResult(ExecutionStatus.SUCCESS, True, "Test reason")

    assert result.should_stop is True
    assert result.status == ExecutionStatus.SUCCESS
    assert result.goal_achieved is True
    assert result.reason == "Test reason"

"""Tools that move the Architect into a mode load that mode's guidance."""

from rhesis.sdk.agents.architect.tool_registry import mode_for
from rhesis.sdk.agents.constants import AgentMode


def test_scheduling_tools_load_the_execution_guidance():
    assert mode_for("schedule_test_set") == AgentMode.EXECUTING
    assert mode_for("run_test_run_schedule_now") == AgentMode.EXECUTING


def test_reading_a_schedule_does_not_change_mode():
    assert mode_for("list_test_run_schedules") is None

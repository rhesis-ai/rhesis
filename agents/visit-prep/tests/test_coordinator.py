"""Coordinator tool wiring and the rule-based red-flag check."""

from haystack.dataclasses import ChatRole

from tests.mocks import greeting_script, make_pipeline, out_of_scope_script, stub_generator
from visit_prep.agents.coordinator import TERMINAL_TOOLS, create_coordinator_agent
from visit_prep.pipeline import run_turn
from visit_prep.state import VisitPrepState
from visit_prep.tools import NO_MESSAGE_TO_SCAN, red_flag_report


def test_red_flag_report_detects_chest_pain():
    assert "RED_FLAG_DETECTED" in red_flag_report("I have chest pain right now")


def test_red_flag_report_clears_benign_text():
    assert "No red flags" in red_flag_report("mild headache for two days")


def test_red_flag_report_handles_empty_text():
    assert red_flag_report("   ") == NO_MESSAGE_TO_SCAN


def test_handoffs_are_not_exit_conditions():
    """The coordinator must see a specialist's result so it can decide what comes next.

    With a handoff as an exit condition the run stops the moment the tool returns, which
    hands the specialist's internal status line straight to the user.
    """
    agent = create_coordinator_agent(generator=stub_generator())
    assert "gather_history" not in agent.exit_conditions
    assert "write_summary" not in agent.exit_conditions
    assert set(TERMINAL_TOOLS) <= set(agent.exit_conditions)


def test_coordinator_exposes_the_expected_tools():
    agent = create_coordinator_agent(generator=stub_generator())
    names = {tool.name for tool in agent.tools}
    assert names == {
        "check_red_flags",
        "escalate",
        "greet_and_explain",
        "redirect_to_scope",
        "gather_history",
        "write_summary",
    }


def test_coordinator_greets_on_hello():
    result = run_turn("hi there", VisitPrepState(), pipeline=make_pipeline(greeting_script()))
    assert result["raw"]["tool_call_counts"].get("greet_and_explain") == 1
    assert "visit-preparation assistant" in result["response"]


def test_coordinator_redirects_diagnosis_request():
    result = run_turn(
        "Just tell me what disease I have",
        VisitPrepState(),
        pipeline=make_pipeline(out_of_scope_script()),
    )
    assert result["raw"]["tool_call_counts"].get("redirect_to_scope") == 1
    assert "diagnose" in result["response"].lower()


def test_check_red_flags_runs_before_the_routing_tool():
    result = run_turn("hi there", VisitPrepState(), pipeline=make_pipeline(greeting_script()))
    tool_names = [
        r.origin.tool_name
        for m in result["raw"]["messages"]
        if m.is_from(ChatRole.TOOL)
        for r in (m.tool_call_results or [])
    ]
    assert tool_names[0] == "check_red_flags"

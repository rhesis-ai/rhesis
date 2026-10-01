from agents import Runner

from docs_assistant.agents.triage import build_triage, scope_view
from docs_assistant.models import model_settings
from docs_assistant.schemas import TriageDecision
from tests.mocks import ScriptedModel, triage, triage_part


def test_scope_view_lists_sections_and_titles(snapshot):
    view = scope_view(snapshot)
    assert "- sdk: SDK Installation & Setup; Overview" in view
    assert "Prompt Injection" in view
    assert "- changelog: Rhesis Changelog" in view


async def test_triage_parses_a_decision_and_uses_no_tools(snapshot):
    model = ScriptedModel(
        [[triage(triage_part("Wie installiere ich das SDK?", surface="sdk"), language="de")]]
    )
    agent = build_triage(model, model_settings("triage"), snapshot)
    result = await Runner.run(agent, "Wie installiere ich das SDK?")

    decision = result.final_output
    assert isinstance(decision, TriageDecision)
    assert decision.language == "de"
    assert decision.parts[0].surface == "sdk"
    assert model.requests[0]["tools"] == []
    assert "What the Rhesis docs cover" in model.requests[0]["system"]

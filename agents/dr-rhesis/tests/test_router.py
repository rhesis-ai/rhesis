from dr_rhesis.agents.router import IntentRouter
from dr_rhesis.state import DrRhesisState
from tests.mocks import MockChatGenerator


def test_router_parses_greeting():
    gen = MockChatGenerator(['{"intent": "greeting"}'])
    router = IntentRouter(generator=gen)
    result = router.run(message="Hi there", state=DrRhesisState())
    assert result["intent"] == "greeting"


def test_router_parses_health_concern():
    gen = MockChatGenerator(['{"intent": "health_concern"}'])
    router = IntentRouter(generator=gen)
    result = router.run(message="My knee hurts", state=DrRhesisState())
    assert result["intent"] == "health_concern"


def test_router_red_flag_message_escalates_without_llm():
    # Empty queue: any generator call would raise, proving the override is
    # deterministic. This phrasing would plausibly be classified out_of_scope
    # (medication request) by the LLM — it must still escalate.
    gen = MockChatGenerator([])
    router = IntentRouter(generator=gen)
    result = router.run(
        message="What medication should I take for this crushing chest pain?",
        state=DrRhesisState(),
    )
    assert result["intent"] == "emergency"
    assert result["raw_json"]["source"] == "red_flag_override"

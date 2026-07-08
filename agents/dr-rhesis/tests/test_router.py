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

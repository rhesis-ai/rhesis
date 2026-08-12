"""Reg-Advisor: ADK multi-agent EU/US health product regulatory assistant."""

from reg_advisor.classify import Determination, classify
from reg_advisor.knowledge import (
    KnowledgeBase,
    RegulationNode,
    get_knowledge_base,
    validate_knowledge_base,
)
from reg_advisor.runner import build_coordinator_agent, build_runner, run_turn, run_turn_async
from reg_advisor.session import (
    StateStore,
    default_store,
    get_default_agent,
    run_chat_turn,
    run_chat_turn_async,
)
from reg_advisor.state import Phase, ProductProfile, RegAdvisorState


def __getattr__(name: str):
    # Lazily loaded so importing the package runs no route or startup code. FastAPI itself still
    # arrives — google-adk depends on it — but building the app is not a library import's job.
    if name == "app":
        from reg_advisor.app import app

        return app
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "Determination",
    "KnowledgeBase",
    "Phase",
    "ProductProfile",
    "RegAdvisorState",
    "RegulationNode",
    "StateStore",
    "app",
    "build_coordinator_agent",
    "build_runner",
    "classify",
    "default_store",
    "get_default_agent",
    "get_knowledge_base",
    "run_chat_turn",
    "run_chat_turn_async",
    "run_turn",
    "run_turn_async",
    "validate_knowledge_base",
]

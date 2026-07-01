"""Microsoft Agent Framework multi-agent travel planner for trace testing."""

from travel_agent.agents import (
    ALL_AGENT_NAMES,
    create_coordinator,
    create_destination_finder,
    create_logistics_planner,
    create_sightseeing_scout,
)
from travel_agent.session import (
    ConversationStore,
    default_store,
    run_chat_turn,
    run_chat_turn_sync,
)
from travel_agent.tools import (
    DESTINATION_TOOLS,
    DESTINATIONS,
    LOGISTICS_TOOLS,
    SIGHTSEEING_TOOLS,
    estimate_travel,
    find_sightseeing,
    get_random_destination,
)
from travel_agent.workflow import (
    build_travel_workflow,
    get_participants,
    get_travel_workflow,
    invoke_travel_workflow,
    invoke_travel_workflow_async,
    run_query,
)


def __getattr__(name: str):
    """Lazy import for ``app`` to avoid circular imports with ``__main__``."""
    if name == "app":
        from travel_agent.app import app

        return app
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "ALL_AGENT_NAMES",
    "DESTINATIONS",
    "DESTINATION_TOOLS",
    "LOGISTICS_TOOLS",
    "SIGHTSEEING_TOOLS",
    "ConversationStore",
    "app",
    "build_travel_workflow",
    "create_coordinator",
    "create_destination_finder",
    "create_logistics_planner",
    "create_sightseeing_scout",
    "default_store",
    "estimate_travel",
    "find_sightseeing",
    "get_participants",
    "get_random_destination",
    "get_travel_workflow",
    "invoke_travel_workflow",
    "invoke_travel_workflow_async",
    "run_chat_turn",
    "run_chat_turn_sync",
    "run_query",
]

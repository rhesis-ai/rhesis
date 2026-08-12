"""Per-agent step budgets.

ADK caps model calls through ``RunConfig(max_llm_calls=...)``, which is no use for a
specialist: ``AgentTool`` builds its own sub-``Runner`` with a default ``RunConfig``, so a
sub-agent never sees the parent's budget. The ADK spike confirmed a child burning four model
calls under a parent budget of two.

So specialists count their own calls in a ``before_model_callback``. Returning an
``LlmResponse`` from that callback skips the model call entirely, which is how the budget is
enforced rather than merely requested.
"""

from __future__ import annotations

from collections.abc import Callable

from google.adk.agents.callback_context import CallbackContext
from google.adk.models import LlmRequest, LlmResponse
from google.genai import types

# `temp:` keys are session-scoped scratch space. The counter is per sub-agent run, and
# `AgentTool` gives each run a fresh child session, so the count starts at zero every time.
COUNTER_PREFIX = "temp:step_count:"


def step_budget(
    limit: int,
    exhausted_reply: str,
) -> Callable[[CallbackContext, LlmRequest], LlmResponse | None]:
    """Build a ``before_model_callback`` that caps this agent at ``limit`` model calls."""

    def enforce(callback_context: CallbackContext, llm_request: LlmRequest) -> LlmResponse | None:
        key = COUNTER_PREFIX + callback_context.agent_name
        used = int(callback_context.state.get(key) or 0)
        if used >= limit:
            return LlmResponse(
                content=types.Content(role="model", parts=[types.Part(text=exhausted_reply)])
            )
        callback_context.state[key] = used + 1
        return None

    return enforce


__all__ = ["COUNTER_PREFIX", "step_budget"]

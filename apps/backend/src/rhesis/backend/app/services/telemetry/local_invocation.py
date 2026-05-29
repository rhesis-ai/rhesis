"""Helpers for invoking ``@endpoint`` functions locally with coherent
conversation tracing.

Two backend call sites drive ``@endpoint``-decorated functions without
going through the SDK connector RPC/WebSocket round-trip:

1. :class:`SdkEndpointInvoker` -- when the registry short-circuits a
   backend-resident function (test execution, playground, REST).
2. ``architect_chat_task`` -- the Celery worker that processes
   production architect chat turns.

Both must bind the SDK telemetry ``ContextVar`` trio
(``conversation_id``, ``conversation_trace_id``,
``conversation_mapped_input``) before invoking the user function so the
SDK tracer reuses the conversation's ``trace_id`` for the root span on
turn 2 and beyond.  Without this, every turn opens a fresh trace and the
UI shows disjointed per-turn traces.

This module centralises that plumbing so the two paths stay in lockstep
when the contract changes.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional

logger = logging.getLogger(__name__)


@asynccontextmanager
async def conversation_telemetry_context(
    conversation_id: Optional[str],
    conversation_trace_id: Optional[str],
    mapped_input: Optional[str],
) -> AsyncIterator[None]:
    """Bind the SDK conversation telemetry ``ContextVar`` trio.

    The SDK tracer (``rhesis.sdk.telemetry.tracer.Tracer``) inspects
    these ContextVars on every root span:

    * ``conversation_trace_id`` -- when set, the tracer reuses this
      32-char hex trace ID instead of generating a new one (see
      ``_build_conversation_parent_context``).
    * ``conversation_id`` -- stamped on the root span as
      ``rhesis.conversation.id`` and used by the linking machinery.
    * ``conversation_mapped_input`` -- stamped on the root span as
      ``rhesis.conversation.input``.

    ``_root_trace_id`` is reset on entry so the inner ``@endpoint``
    tracer treats this call as the root span; all four ContextVars are
    cleared on exit so they do not leak into subsequent calls that
    share the same asyncio task.
    """
    from rhesis.sdk.telemetry.context import (
        set_conversation_id,
        set_conversation_mapped_input,
        set_conversation_trace_id,
        set_root_trace_id,
    )

    if conversation_id:
        set_conversation_id(conversation_id)
    if conversation_trace_id:
        set_conversation_trace_id(conversation_trace_id)
    if mapped_input:
        set_conversation_mapped_input(mapped_input)
    set_root_trace_id(None)
    try:
        yield
    finally:
        set_conversation_id(None)
        set_conversation_trace_id(None)
        set_conversation_mapped_input(None)
        set_root_trace_id(None)

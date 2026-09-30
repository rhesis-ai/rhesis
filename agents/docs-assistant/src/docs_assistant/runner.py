"""Run one docs assistant turn.

For now every message goes straight to the answer agent (triage arrives with the other routes).
Whatever happens inside the run, the user only ever sees a draft that passed the grounding
checks, or the fixed fallback reply.
"""

from __future__ import annotations

import asyncio
import logging
import uuid

from agents import MaxTurnsExceeded, Model, Runner

from docs_assistant import compose
from docs_assistant.agents.answerer import (
    NUDGE,
    BudgetHooks,
    TokenBudgetExceeded,
    build_answerer,
)
from docs_assistant.config import Settings, get_settings
from docs_assistant.context import TurnContext
from docs_assistant.corpus.cache import CorpusCache
from docs_assistant.models import build_model, configure_sdk, model_settings
from docs_assistant.schemas import AnswerDraft, RelatedPage, Route, TurnResponse

logger = logging.getLogger(__name__)

FALLBACK_REPLY = (
    "I couldn't finish checking the docs for this question, so I won't guess. "
    "Try a narrower question, or start from the pages below."
)
NO_SUBMIT_REPLY = (
    "I couldn't put together an answer I could check against the docs, so I won't guess. "
    "The pages below are the closest matches."
)
FALLBACK_RELATED = 3


async def run_turn(
    message: str,
    *,
    cache: CorpusCache,
    model: Model | None = None,
    settings: Settings | None = None,
    conversation_id: str | None = None,
) -> TurnResponse:
    """Answer one message. Raises `DocsUnavailable` when there is no docs snapshot at all."""
    configure_sdk()
    settings = settings or get_settings()
    snapshot = await cache.get()
    ctx = TurnContext(snapshot=snapshot, settings=settings, cache=cache)
    agent = build_answerer(model or build_model("answer"), model_settings("answer"))
    draft = await _answer(agent, message, ctx) or _fallback(ctx)
    return _response(draft, ctx, cache, conversation_id)


async def _answer(agent, message: str, ctx: TurnContext) -> AnswerDraft | None:
    try:
        return await asyncio.wait_for(
            _run_with_nudge(agent, message, ctx), timeout=ctx.settings.turn_timeout
        )
    except TimeoutError:
        ctx.hit_limit("timeout")
    except MaxTurnsExceeded:
        ctx.hit_limit("max_turns")
    except TokenBudgetExceeded:
        pass  # BudgetHooks already recorded the limit.
    return ctx.accepted


async def _run_with_nudge(agent, message: str, ctx: TurnContext) -> AnswerDraft | None:
    run = {"context": ctx, "max_turns": ctx.settings.max_turns, "hooks": BudgetHooks()}
    result = await Runner.run(agent, message, **run)
    if ctx.accepted is None:
        # The model ended with plain text instead of submitting. That text was never checked,
        # so it is dropped; the model gets one reminder, then the fallback takes over.
        logger.info("Answer agent ended without submit_answer; nudging once")
        follow_up = result.to_input_list() + [{"role": "user", "content": NUDGE}]
        await Runner.run(agent, follow_up, **run)
    if ctx.accepted is None:
        ctx.hit_limit("no_submit")
    return ctx.accepted


def _fallback(ctx: TurnContext) -> AnswerDraft:
    related, seen = [], set()
    for hit in ctx.search_hits:
        if hit.url not in seen and len(related) < FALLBACK_RELATED:
            seen.add(hit.url)
            related.append(RelatedPage(title=hit.title, url=hit.url))
    reply = NO_SUBMIT_REPLY if ctx.limits_hit == ["no_submit"] else FALLBACK_REPLY
    return AnswerDraft(
        route="not_documented",
        answer_md=reply,
        claims=[],
        citations=[],
        undocumented=[],
        premise_correction=None,
        related_pages=related,
    )


def _response(
    draft: AnswerDraft, ctx: TurnContext, cache: CorpusCache, conversation_id: str | None
) -> TurnResponse:
    citations = compose.citations_for(draft, ctx.snapshot, ctx.ledger)
    related = compose.related_pages_for(draft, ctx.snapshot)
    return TurnResponse(
        conversation_id=conversation_id or uuid.uuid4().hex,
        turn=1,
        route=Route(draft.route),
        response=compose.render(draft, citations, related),
        answer_md=draft.answer_md,
        citations=citations,
        undocumented=draft.undocumented,
        premise_correction=draft.premise_correction,
        related_pages=related,
        docs_as_of=ctx.snapshot.fetched_at,
        docs_stale=cache.stale,
        limits_hit=ctx.limits_hit,
        answer_id=uuid.uuid4().hex,
    )

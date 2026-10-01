"""Run one docs assistant turn: precheck → triage → answer → compose.

Python decides the route; the models only propose. A precheck hit or a non-docs triage verdict
ends in a fixed reply with no docs read. Whatever happens inside the answer run, the user only
ever sees a draft that passed the grounding checks, or the fixed fallback reply.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Sequence

from agents import MaxTurnsExceeded, Runner

from docs_assistant import compose, safety, terminals
from docs_assistant.agents import answerer, triage
from docs_assistant.agents.answerer import (
    NUDGE,
    BudgetHooks,
    TokenBudgetExceeded,
    build_answerer,
    question_input,
)
from docs_assistant.agents.triage import build_triage
from docs_assistant.config import Settings, get_settings
from docs_assistant.context import TurnContext
from docs_assistant.corpus.cache import CorpusCache, Snapshot
from docs_assistant.models import AgentModels, configure_sdk, model_settings
from docs_assistant.schemas import (
    AnswerDraft,
    NextStep,
    RelatedPage,
    Route,
    TriageDecision,
    TriagePart,
    TurnResponse,
)

logger = logging.getLogger(__name__)

FALLBACK_RELATED = 3
# When kinds clash across parts, the most severe fixed reply wins.
TERMINAL_PRIORITY = ("account_or_support", "out_of_scope", "smalltalk")
TERMINAL_ROUTES = {
    "unsafe": Route.UNSAFE_OR_INJECTION,
    "account_or_support": Route.ACCOUNT_OR_SUPPORT,
    "out_of_scope": Route.OUT_OF_SCOPE,
    "smalltalk": Route.SMALLTALK,
    "thanks": Route.SMALLTALK,
    "empty": Route.SMALLTALK,
}


class _Turn:
    """What one turn has learned so far, shared by the steps below."""

    def __init__(self, snapshot: Snapshot, cache: CorpusCache, settings: Settings) -> None:
        self.snapshot = snapshot
        self.cache = cache
        self.settings = settings
        self.deadline = asyncio.get_running_loop().time() + settings.turn_timeout
        self.language = "en"
        self.surface = "unknown"
        self.limits_hit: list[str] = []
        self.notes: list[str] = []

    def remaining(self) -> float:
        return max(self.deadline - asyncio.get_running_loop().time(), 0.0)

    def hit_limit(self, name: str) -> None:
        if name not in self.limits_hit:
            self.limits_hit.append(name)


async def run_turn(
    message: str,
    *,
    cache: CorpusCache,
    models: AgentModels | None = None,
    settings: Settings | None = None,
    conversation_id: str | None = None,
) -> TurnResponse:
    """Answer one message. Raises `DocsUnavailable` when there is no docs snapshot at all."""
    configure_sdk()
    settings = settings or get_settings()
    turn = _Turn(await cache.get(), cache, settings)
    text, clipped = safety.clip(message, settings.max_input_chars)
    if verdict := safety.precheck(text):
        turn.language = verdict.language
        return _terminal(turn, verdict.kind, conversation_id)

    models = models or AgentModels.from_env()
    decision = await _triage(models, text, turn)
    turn.language = decision.language or "en"
    if clipped:
        turn.hit_limit("input_clipped")
        turn.notes.append(terminals.text("input_clipped", turn.language, n=len(text)))
    parts = decision.parts[: settings.max_parts] or [_docs_part(text)]
    if len(decision.parts) > settings.max_parts:
        turn.hit_limit("parts_capped")
        turn.notes.append(terminals.text("parts_capped", turn.language, n=settings.max_parts))

    kinds = [p.kind for p in parts]
    if "unsafe" in kinds:
        return _terminal(turn, "unsafe", conversation_id)
    docs_parts = [p for p in parts if p.kind == "docs"]
    if not docs_parts:
        kind = next(k for k in TERMINAL_PRIORITY if k in kinds)
        if kind == "account_or_support":
            return await _support(models, parts, decision, turn, conversation_id)
        return _terminal(turn, kind, conversation_id)

    part = docs_parts[0]
    turn.surface = part.surface
    draft, ctx = await _answer_part(models, part, turn)
    return _answer_response(draft, ctx, turn, conversation_id)


# ── triage ───────────────────────────────────────────────────────────────────────────────


def _docs_part(question: str) -> TriagePart:
    return TriagePart(
        standalone_question=question, kind="docs", surface="unknown", in_scope_uncertain=True
    )


async def _triage(models: AgentModels, text: str, turn: _Turn) -> TriageDecision:
    """Triage's verdict. If triage fails, the message goes to the answer agent as one part:
    wrongly declining a Rhesis question is worse than checking the docs for nothing."""
    agent = build_triage(models.triage, model_settings("triage"), turn.snapshot)
    try:
        result = await asyncio.wait_for(Runner.run(agent, text), timeout=turn.remaining())
        return result.final_output
    except Exception:
        logger.warning("Triage failed; sending the message to the answer agent", exc_info=True)
        return TriageDecision(
            parts=[_docs_part(text)],
            language=safety.guess_language(text),
            wants_troubleshooting=False,
        )


# ── answer ───────────────────────────────────────────────────────────────────────────────


async def _answer_part(
    models: AgentModels, part: TriagePart, turn: _Turn, *, troubleshooting: bool = False
) -> tuple[AnswerDraft, TurnContext]:
    ctx = TurnContext(snapshot=turn.snapshot, settings=turn.settings, cache=turn.cache)
    agent = build_answerer(models.answer, model_settings("answer"))
    prompt = question_input(
        part.standalone_question, turn.language, part.surface, troubleshooting=troubleshooting
    )
    draft = await _answer(agent, prompt, ctx, turn.remaining()) or _fallback(ctx, turn.language)
    for limit in ctx.limits_hit:
        turn.hit_limit(limit)
    return draft, ctx


async def _answer(agent, prompt: str, ctx: TurnContext, timeout: float) -> AnswerDraft | None:
    try:
        return await asyncio.wait_for(_run_with_nudge(agent, prompt, ctx), timeout=timeout)
    except TimeoutError:
        ctx.hit_limit("timeout")
    except MaxTurnsExceeded:
        ctx.hit_limit("max_turns")
    except TokenBudgetExceeded:
        pass  # BudgetHooks already recorded the limit.
    return ctx.accepted


async def _run_with_nudge(agent, prompt: str, ctx: TurnContext) -> AnswerDraft | None:
    run = {"context": ctx, "max_turns": ctx.settings.max_turns, "hooks": BudgetHooks()}
    result = await Runner.run(agent, prompt, **run)
    if ctx.accepted is None:
        # The model ended with plain text instead of submitting. That text was never checked,
        # so it is dropped; the model gets one reminder, then the fallback takes over.
        logger.info("Answer agent ended without submit_answer; nudging once")
        follow_up = result.to_input_list() + [{"role": "user", "content": NUDGE}]
        await Runner.run(agent, follow_up, **run)
    if ctx.accepted is None:
        ctx.hit_limit("no_submit")
    return ctx.accepted


def _fallback(ctx: TurnContext, language: str) -> AnswerDraft:
    reply = "no_submit" if ctx.limits_hit == ["no_submit"] else "fallback"
    return AnswerDraft(
        route="not_documented",
        answer_md=terminals.text(reply, language),
        claims=[],
        citations=[],
        undocumented=[],
        premise_correction=None,
        related_pages=_searched_pages(ctx),
    )


def _searched_pages(ctx: TurnContext) -> list[RelatedPage]:
    return _unique_pages([RelatedPage(title=h.title, url=h.url) for h in ctx.search_hits])[
        :FALLBACK_RELATED
    ]


def _unique_pages(pages: list[RelatedPage]) -> list[RelatedPage]:
    unique: dict[str, RelatedPage] = {}
    for page in pages:
        unique.setdefault(page.url, page)
    return list(unique.values())


def _screen(draft: AnswerDraft) -> AnswerDraft | None:
    """None when the reply repeats our own prompt; otherwise the draft minus any line carrying
    an internal status word."""
    prompts = [answerer.INSTRUCTIONS, triage.INSTRUCTIONS.split("{scope}")[0]]
    if safety.leaks_prompt(draft.answer_md, prompts):
        logger.warning("Answer repeated the system prompt; replacing it with the decline")
        return None
    return draft.model_copy(update={"answer_md": safety.strip_status_lines(draft.answer_md)})


# ── responses ────────────────────────────────────────────────────────────────────────────


def _answer_response(
    draft: AnswerDraft, ctx: TurnContext, turn: _Turn, conversation_id: str | None
) -> TurnResponse:
    screened = _screen(draft)
    if screened is None:
        return _terminal(turn, "unsafe", conversation_id)
    citations = compose.citations_for(screened, ctx.snapshot, ctx.ledger)
    related = compose.related_pages_for(screened, ctx.snapshot)
    next_steps = terminals.SUPPORT_STEPS if screened.route == "not_documented" else []
    response = compose.render(
        screened,
        citations,
        related,
        language=turn.language,
        next_steps=next_steps,
        notes=turn.notes,
    )
    return _response(
        turn,
        conversation_id,
        route=Route(screened.route),
        response=response,
        answer_md=screened.answer_md,
        citations=citations,
        undocumented=screened.undocumented,
        premise_correction=screened.premise_correction,
        related_pages=related,
        next_steps=next_steps,
    )


async def _support(
    models: AgentModels,
    parts: list[TriagePart],
    decision: TriageDecision,
    turn: _Turn,
    conversation_id: str | None,
) -> TurnResponse:
    """Support links always; with `wants_troubleshooting`, also the docs pages that may help.
    The route stays account_or_support either way."""
    related: list[RelatedPage] = []
    if decision.wants_troubleshooting:
        part = next(p for p in parts if p.kind == "account_or_support")
        draft, ctx = await _answer_part(models, part, turn, troubleshooting=True)
        cited = [
            RelatedPage(title=c.title, url=c.url.split("#", 1)[0])
            for c in compose.citations_for(draft, ctx.snapshot, ctx.ledger)
        ]
        related = _unique_pages(cited + compose.related_pages_for(draft, ctx.snapshot))
    body = [terminals.support(turn.language), terminals.links(terminals.SUPPORT_STEPS)]
    if related:
        body += [terminals.text("support_pages", turn.language), compose.related_list(related)]
    return _response(
        turn,
        conversation_id,
        route=Route.ACCOUNT_OR_SUPPORT,
        response=_with_notes(turn, "\n\n".join(body)),
        related_pages=related,
        next_steps=terminals.SUPPORT_STEPS,
    )


def _terminal(turn: _Turn, kind: str, conversation_id: str | None) -> TurnResponse:
    match kind:
        case "unsafe":
            body = terminals.unsafe(turn.language)
        case "out_of_scope":
            body = terminals.out_of_scope(turn.language)
        case "thanks":
            body = terminals.smalltalk(turn.language, thanks=True)
        case "empty":
            body = terminals.text("empty", turn.language)
        case _:
            body = terminals.smalltalk(turn.language)
    # An unsafe turn carries no notes: nothing about the attempt is echoed back.
    response = body if kind == "unsafe" else _with_notes(turn, body)
    return _response(turn, conversation_id, route=TERMINAL_ROUTES[kind], response=response)


def _with_notes(turn: _Turn, body: str) -> str:
    return "\n\n".join([*(f"_{n}_" for n in turn.notes), body])


def _response(
    turn: _Turn,
    conversation_id: str | None,
    *,
    route: Route,
    response: str,
    answer_md: str | None = None,
    next_steps: Sequence[NextStep] = (),
    **fields,
) -> TurnResponse:
    return TurnResponse(
        conversation_id=conversation_id or uuid.uuid4().hex,
        turn=1,
        route=route,
        response=response,
        answer_md=response if answer_md is None else answer_md,
        citations=fields.pop("citations", []),
        next_steps=list(next_steps),
        surface=turn.surface,
        language=turn.language,
        docs_as_of=turn.snapshot.fetched_at,
        docs_stale=turn.cache.stale,
        limits_hit=turn.limits_hit,
        answer_id=uuid.uuid4().hex,
        **fields,
    )

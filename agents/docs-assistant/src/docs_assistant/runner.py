"""Run one docs assistant turn: precheck → triage → answer each part → compose.

Python decides the route; the models only propose. A precheck hit or a non-docs triage verdict
ends in a fixed reply with no docs read. Whatever happens inside an answer run, the user only
ever sees a draft that passed the grounding checks, or the fixed fallback reply.

Each turn runs under its conversation's lock, so follow-ups see the turns before them.
"""

from __future__ import annotations

import asyncio
import logging
import uuid

from agents import MaxTurnsExceeded, OutputGuardrailTripwireTriggered, Runner
from openai import APIError

from docs_assistant import compose, grounding, safety, terminals
from docs_assistant.agents import answerer, critic, triage
from docs_assistant.agents.answerer import (
    NUDGE,
    BudgetHooks,
    TokenBudgetExceeded,
    build_answerer,
    question_input,
)
from docs_assistant.agents.triage import build_triage, triage_input
from docs_assistant.compose import PartOutcome
from docs_assistant.config import Settings, get_settings
from docs_assistant.context import TokenMeter, TurnContext
from docs_assistant.corpus.cache import CorpusCache, Snapshot
from docs_assistant.corpus.parser import canonical_url
from docs_assistant.grounding import MAX_OPTIONS, MIN_OPTIONS
from docs_assistant.models import AgentModels, configure_sdk, model_settings
from docs_assistant.schemas import (
    AnswerDraft,
    Clarification,
    ConflictNote,
    RelatedPage,
    Route,
    TriageDecision,
    TriagePart,
    TurnResponse,
)
from docs_assistant.session import ConversationStore, Store
from docs_assistant.state import (
    ConversationState,
    PendingClarification,
    TurnRecord,
    match_option,
)

logger = logging.getLogger(__name__)

FALLBACK_RELATED = 3
# Routes whose claims the critic checks; the others make no claims.
CRITIC_ROUTES = {"answered", "partially_answered", "false_premise"}
# When kinds clash across parts with no docs part, the most severe fixed reply wins.
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

    def __init__(
        self,
        snapshot: Snapshot,
        cache: CorpusCache,
        settings: Settings,
        state: ConversationState,
    ) -> None:
        self.snapshot = snapshot
        self.cache = cache
        self.settings = settings
        self.state = state
        self.deadline = asyncio.get_running_loop().time() + settings.turn_timeout
        self.language = "en"
        self.surface = "unknown"
        self.limits_hit: list[str] = []
        self.notes: list[str] = []
        # What the conversation remembers of this turn: the standalone question(s).
        self.question = ""
        self.tokens = TokenMeter()
        self.allow_clarify = state.clarify_streak < settings.max_clarify_streak

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
    store: Store | None = None,
) -> TurnResponse:
    """Answer one message. Raises `DocsUnavailable` when there is no docs snapshot at all.

    Without a store the turn stands alone, as if it opened a new conversation."""
    configure_sdk()
    settings = settings or get_settings()
    snapshot = await cache.get()
    async with (store or ConversationStore()).turn(conversation_id) as state:
        turn = _Turn(snapshot, cache, settings, state)
        response = await _run(message, turn, models)
        _remember(state, response, turn)
        return response


async def _run(message: str, turn: _Turn, models: AgentModels | None) -> TurnResponse:
    settings = turn.settings
    text, clipped = safety.clip(message, settings.max_input_chars)
    if verdict := safety.precheck(text):
        turn.language = verdict.language
        return _terminal(turn, verdict.kind, text)

    models = models or AgentModels.from_env(critic=settings.critic)
    pending = turn.state.pending
    option = match_option(text, pending.clarification.options) if pending else None
    if option:
        # A reply to our clarifying question: answer the original question with that reading.
        turn.language = pending.language
        parts = [_docs_part(f"{pending.question} ({option})", pending.surface)]
        decision = None
    else:
        decision = await _triage(models, text, turn)
        turn.language = decision.language or "en"
        parts = decision.parts or [_docs_part(text)]
    if clipped:
        turn.hit_limit("input_clipped")
        turn.notes.append(terminals.text("input_clipped", turn.language, n=len(text)))
    if len(parts) > settings.max_parts:
        turn.hit_limit("parts_capped")
        turn.notes.append(terminals.text("parts_capped", turn.language, n=settings.max_parts))
        parts = parts[: settings.max_parts]

    kinds = [p.kind for p in parts]
    if "unsafe" in kinds:
        return _terminal(turn, "unsafe", text)
    docs_parts = [p for p in parts if p.kind == "docs"]
    if not docs_parts:
        kind = next(k for k in TERMINAL_PRIORITY if k in kinds)
        if kind == "account_or_support":
            return await _support(models, parts, decision, turn)
        return _terminal(turn, kind, text)
    if decision and (clarification := _triage_clarification(decision, docs_parts, turn)):
        return _clarify(turn, docs_parts[0], clarification)
    return await _answer_parts(models, parts, turn)


# ── triage ───────────────────────────────────────────────────────────────────────────────


def _docs_part(question: str, surface: str = "unknown") -> TriagePart:
    return TriagePart(
        standalone_question=question, kind="docs", surface=surface, in_scope_uncertain=True
    )


async def _triage(models: AgentModels, text: str, turn: _Turn) -> TriageDecision:
    """Triage's verdict. If triage fails, the message goes to the answer agent as one part:
    wrongly declining a Rhesis question is worse than checking the docs for nothing."""
    agent = build_triage(models.triage, model_settings("triage"), turn.snapshot)
    prompt = triage_input(text, turn.state.history())
    try:
        result = await asyncio.wait_for(Runner.run(agent, prompt), timeout=turn.remaining())
        return result.final_output
    except Exception:
        logger.warning("Triage failed; sending the message to the answer agent", exc_info=True)
        return TriageDecision(
            parts=[_docs_part(text)],
            language=safety.guess_language(text),
            wants_troubleshooting=False,
            clarification=None,
        )


def _triage_clarification(
    decision: TriageDecision, docs_parts: list[TriagePart], turn: _Turn
) -> Clarification | None:
    """Triage's clarifying question, if one is allowed now: a single docs part, a well-formed
    question, and no clarification on the turn just before."""
    clarification = decision.clarification
    if clarification is None or len(docs_parts) != 1 or len(decision.parts) != 1:
        return None
    options = [o.strip() for o in clarification.options if o.strip()]
    if not (MIN_OPTIONS <= len(options) <= MAX_OPTIONS and clarification.question.strip()):
        return None
    if not turn.allow_clarify:
        turn.hit_limit("clarify_streak")
        return None
    return Clarification(question=clarification.question.strip(), options=options)


# ── answer ───────────────────────────────────────────────────────────────────────────────


async def _answer_parts(models: AgentModels, parts: list[TriagePart], turn: _Turn) -> TurnResponse:
    """Run every docs part in parallel on the turn's shared time and token budget, then merge.
    Other parts get their short fixed text; a greeting next to a real question is dropped."""
    docs_parts = [p for p in parts if p.kind == "docs"]
    turn.surface = _surface(docs_parts)
    answered = iter(await asyncio.gather(*(_answer_part(models, p, turn) for p in docs_parts)))
    outcomes = []
    for part in parts:
        if part.kind == "docs":
            draft, ctx = next(answered)
            outcomes.append(_docs_outcome(part, draft, ctx))
        elif part.kind != "smalltalk":
            outcomes.append(_fixed_outcome(part, turn.language))
    if any(o.route is Route.UNSAFE_OR_INJECTION for o in outcomes):
        return _terminal(turn, "unsafe", "")
    if len(outcomes) == 1 and (draft := outcomes[0].draft) and draft.clarification:
        if draft.route == "needs_clarification":
            return _clarify(turn, docs_parts[0], draft.clarification)
    return _compose(turn, outcomes)


def _surface(parts: list[TriagePart]) -> str:
    surfaces = {p.surface for p in parts} - {"unknown"}
    return surfaces.pop() if len(surfaces) == 1 else ("both" if surfaces else "unknown")


async def _answer_part(
    models: AgentModels, part: TriagePart, turn: _Turn, *, troubleshooting: bool = False
) -> tuple[AnswerDraft, TurnContext]:
    ctx = TurnContext(
        snapshot=turn.snapshot,
        settings=turn.settings,
        cache=turn.cache,
        allow_clarify=turn.allow_clarify and not troubleshooting,
        tokens=turn.tokens,
    )
    agent = build_answerer(models.answer, model_settings("answer"))
    prompt = question_input(
        part.standalone_question,
        turn.language,
        part.surface,
        troubleshooting=troubleshooting,
        allow_clarify=ctx.allow_clarify,
    )
    draft = await _answer(agent, prompt, ctx, turn.remaining())
    if draft is not None and not troubleshooting:
        draft = await _review(models, agent, prompt, draft, ctx, turn)
    draft = draft or _fallback(ctx, turn.language)
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
    except OutputGuardrailTripwireTriggered:
        logger.error("Backstop guardrail tripped on an accepted draft; sending the fallback")
        ctx.hit_limit("backstop")
        ctx.accepted = None
    except APIError:
        # The provider failed mid-run (connection, rate limit, 5xx). Keep any accepted draft;
        # otherwise the fallback says so instead of a 500.
        logger.warning("Model call failed during the answer run", exc_info=True)
        ctx.hit_limit("model_error")
    return ctx.accepted


async def _run_with_nudge(agent, prompt: str, ctx: TurnContext) -> AnswerDraft | None:
    run = {"context": ctx, "max_turns": ctx.settings.max_turns, "hooks": BudgetHooks()}
    result = await Runner.run(agent, prompt, **run)
    if ctx.accepted is None and not ctx.gave_up:
        # The model ended with plain text instead of submitting. That text was never checked,
        # so it is dropped; the model gets one reminder, then the fallback takes over.
        logger.info("Answer agent ended without submit_answer; nudging once")
        follow_up = result.to_input_list() + [{"role": "user", "content": NUDGE}]
        await Runner.run(agent, follow_up, **run)
    if ctx.accepted is None and not ctx.gave_up:
        ctx.hit_limit("no_submit")
    return ctx.accepted


async def _review(
    models: AgentModels, agent, prompt: str, draft: AnswerDraft, ctx: TurnContext, turn: _Turn
) -> AnswerDraft | None:
    """The critic's veto: one re-run of the answer agent with its feedback; if it still finds
    unsupported claims, Python drops them. None means nothing supported is left."""
    if models.critic is None or not turn.settings.critic or draft.route not in CRITIC_ROUTES:
        return draft
    verdict = await _criticize(models, draft, ctx, turn)
    if verdict is None:
        return draft
    vetoed = critic.unsupported(verdict, len(draft.claims))
    if not vetoed and verdict.route_ok:
        return draft
    ctx.hit_limit("critic_veto")
    ctx.accepted, ctx.rejections = None, 0
    note = critic.feedback(draft, vetoed, verdict.route_ok)
    retry = await _answer(agent, f"{prompt}\n\n{note}", ctx, turn.remaining())
    if retry is not None:
        second = await _criticize(models, retry, ctx, turn)
        retry_vetoed = critic.unsupported(second, len(retry.claims)) if second else {}
        if retry.route not in CRITIC_ROUTES or not retry_vetoed:
            return retry
        draft, vetoed = retry, retry_vetoed
    if not vetoed:
        return draft
    return grounding.drop_claims(draft, set(range(len(draft.claims))) - set(vetoed))


async def _criticize(models: AgentModels, draft: AnswerDraft, ctx: TurnContext, turn: _Turn):
    """The critic's verdict, or None if it failed: the code checks already passed, so a broken
    critic leaves the draft as it is."""
    if draft.route not in CRITIC_ROUTES:
        return None
    agent = critic.build_critic(models.critic, model_settings("critic"))
    try:
        result = await asyncio.wait_for(
            Runner.run(agent, critic.critic_input(draft, ctx.ledger)), timeout=turn.remaining()
        )
        return result.final_output
    except Exception:
        logger.warning("Critic failed; keeping the checked draft", exc_info=True)
        ctx.hit_limit("critic_unavailable")
        return None


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
        clarification=None,
        adapted_code=[],
        conflicts=[],
    )


def _searched_pages(ctx: TurnContext) -> list[RelatedPage]:
    pages = [RelatedPage(title=h.title, url=h.url) for h in ctx.search_hits]
    return compose.unique_pages(pages)[:FALLBACK_RELATED]


def _screen(draft: AnswerDraft) -> AnswerDraft | None:
    """None when the reply repeats our own prompt; otherwise the draft minus any line carrying
    an internal status word."""
    prompts = [answerer.INSTRUCTIONS, triage.INSTRUCTIONS.split("{scope}")[0]]
    if safety.leaks_prompt(draft.answer_md, prompts):
        logger.warning("Answer repeated the system prompt; replacing it with the decline")
        return None
    return draft.model_copy(update={"answer_md": safety.strip_status_lines(draft.answer_md)})


def _docs_outcome(part: TriagePart, draft: AnswerDraft, ctx: TurnContext) -> PartOutcome:
    screened = _screen(draft)
    if screened is None:
        return PartOutcome(part.standalone_question, Route.UNSAFE_OR_INJECTION)
    adapted = [
        RelatedPage(title=page.title, url=page.url)
        for a in screened.adapted_code
        if (page := ctx.ledger.get(canonical_url(a.source_url)))
    ]
    return PartOutcome(
        question=part.standalone_question,
        route=Route(screened.route),
        draft=screened,
        citations=compose.citations_for(screened, ctx.snapshot, ctx.ledger),
        related=compose.related_pages_for(screened, ctx.snapshot),
        adapted=compose.unique_pages(adapted),
    )


def _fixed_outcome(part: TriagePart, language: str) -> PartOutcome:
    if part.kind == "account_or_support":
        text = f"{terminals.support(language)}\n{terminals.links(terminals.SUPPORT_STEPS)}"
    else:
        text = terminals.text("out_of_scope", language)
    return PartOutcome(part.standalone_question, TERMINAL_ROUTES[part.kind], text=text)


# ── responses ────────────────────────────────────────────────────────────────────────────


def _compose(turn: _Turn, outcomes: list[PartOutcome]) -> TurnResponse:
    citations = compose.unique_citations(outcomes)
    related = compose.unique_pages([page for o in outcomes for page in o.related])
    routes = [o.route for o in outcomes]
    needs_help = {Route.NOT_DOCUMENTED, Route.ACCOUNT_OR_SUPPORT} & set(routes)
    next_steps = terminals.SUPPORT_STEPS if needs_help else []
    response = compose.render(
        outcomes,
        citations,
        related,
        language=turn.language,
        next_steps=next_steps if Route.NOT_DOCUMENTED in routes else [],
        notes=turn.notes,
        docs_as_of=turn.snapshot.fetched_at,
        stale=turn.cache.stale,
    )
    drafts = [o.draft for o in outcomes if o.draft]
    return _response(
        turn,
        route=compose.turn_route(routes),
        response=response,
        question=" / ".join(o.question for o in outcomes),
        answer_md="\n\n".join(d.answer_md for d in drafts),
        citations=citations,
        undocumented=[gap for d in drafts for gap in d.undocumented],
        premise_correction=next(
            (d.premise_correction for d in drafts if d.premise_correction), None
        ),
        related_pages=related,
        parts=[_part_result(o) for o in outcomes],
        conflicts=[note for o in outcomes for note in _conflicts(o)],
        next_steps=next_steps,
    )


def _conflicts(outcome: PartOutcome) -> list[ConflictNote]:
    draft = outcome.draft
    if draft is None:
        return []
    return [
        ConflictNote(summary=c.summary, urls=compose.cited_urls(draft, c.citation_ids))
        for c in draft.conflicts
    ]


def _part_result(outcome: PartOutcome) -> dict:
    draft = outcome.draft
    return {
        "conflicts": _conflicts(outcome),
        "question": outcome.question,
        "route": outcome.route,
        "answer_md": draft.answer_md if draft else outcome.text,
        "citations": outcome.citations,
        "undocumented": draft.undocumented if draft else [],
        "premise_correction": draft.premise_correction if draft else None,
        "related_pages": outcome.related,
    }


def _clarify(turn: _Turn, part: TriagePart, clarification: Clarification) -> TurnResponse:
    turn.surface = part.surface
    text = compose.render_clarification(clarification, turn.language)
    return _response(
        turn,
        route=Route.NEEDS_CLARIFICATION,
        response="\n\n".join([*(f"_{n}_" for n in turn.notes), text]),
        question=part.standalone_question,
        clarification=clarification,
    )


async def _support(
    models: AgentModels, parts: list[TriagePart], decision: TriageDecision | None, turn: _Turn
) -> TurnResponse:
    """Support links always; with `wants_troubleshooting`, also the docs pages that may help.
    The route stays account_or_support either way."""
    part = next(p for p in parts if p.kind == "account_or_support")
    related: list[RelatedPage] = []
    if decision and decision.wants_troubleshooting:
        draft, ctx = await _answer_part(models, part, turn, troubleshooting=True)
        cited = [
            RelatedPage(title=c.title, url=c.url.split("#", 1)[0])
            for c in compose.citations_for(draft, ctx.snapshot, ctx.ledger)
        ]
        related = compose.unique_pages(cited + compose.related_pages_for(draft, ctx.snapshot))
    body = [terminals.support(turn.language), terminals.links(terminals.SUPPORT_STEPS)]
    if related:
        body += [terminals.text("support_pages", turn.language), compose.related_list(related)]
        body.append(compose.footer(turn.snapshot.fetched_at, turn.cache.stale, turn.language))
    return _response(
        turn,
        route=Route.ACCOUNT_OR_SUPPORT,
        response=_with_notes(turn, "\n\n".join(body)),
        question=part.standalone_question,
        related_pages=related,
        next_steps=terminals.SUPPORT_STEPS,
    )


def _terminal(turn: _Turn, kind: str, question: str) -> TurnResponse:
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
    return _response(turn, route=TERMINAL_ROUTES[kind], response=response, question=question)


def _with_notes(turn: _Turn, body: str) -> str:
    return "\n\n".join([*(f"_{n}_" for n in turn.notes), body])


def _response(turn: _Turn, *, route: Route, response: str, question: str, **fields) -> TurnResponse:
    turn.question = question
    fields.setdefault("answer_md", response)
    fields.setdefault("citations", [])
    return TurnResponse(
        conversation_id=turn.state.conversation_id,
        turn=turn.state.turn + 1,
        route=route,
        response=response,
        surface=turn.surface,
        language=turn.language,
        docs_as_of=turn.snapshot.fetched_at,
        docs_stale=turn.cache.stale,
        limits_hit=turn.limits_hit,
        answer_id=uuid.uuid4().hex,
        **fields,
    )


def _remember(state: ConversationState, response: TurnResponse, turn: _Turn) -> None:
    """Record the turn. An unsafe turn changes nothing, so it can't steer later turns."""
    if response.route is Route.UNSAFE_OR_INJECTION:
        return
    state.turns.append(
        TurnRecord(
            question=turn.question,
            route=response.route.value,
            cited_urls=[c.url for c in response.citations],
        )
    )
    if response.clarification:
        state.pending = PendingClarification(
            question=turn.question,
            clarification=response.clarification,
            language=response.language,
            surface=turn.surface,
        )
        state.clarify_streak += 1
    else:
        state.pending = None
        state.clarify_streak = 0

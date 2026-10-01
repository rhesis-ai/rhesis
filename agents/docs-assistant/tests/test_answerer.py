from docs_assistant.agents.answerer import NUDGE
from docs_assistant.runner import run_turn
from docs_assistant.schemas import Route
from docs_assistant.terminals import text as reply
from tests.mocks import ScriptedModel, draft, fetch, models, search, submit, text

SCOPE = "https://docs.rhesis.ai/docs/metrics/metric-scope"


async def turn(model, cache, settings, message="What is metric scope?"):
    return await run_turn(message, cache=cache, models=models(model), settings=settings)


async def test_search_fetch_submit_gives_a_cited_answer(cache, settings):
    model = ScriptedModel([[search("metric scope")], [fetch(SCOPE)], [submit()]])
    response = await turn(model, cache, settings)

    assert response.route is Route.ANSWERED
    assert [c.url for c in response.citations] == [f"{SCOPE}#when-to-use-multi-turn"]
    assert response.citations[0].title == "Metric scope"
    assert response.citations[0].heading == 'When to use `["Multi-Turn"]`'
    # The inline [c1] marker becomes a numbered link to the source.
    assert f"[\\[1\\]]({SCOPE}#when-to-use-multi-turn)" in response.response
    assert "**Sources**" in response.response
    assert response.limits_hit == []
    assert len(model.requests) == 3
    assert model.requests[0]["tools"] == [
        "search_docs",
        "fetch_page",
        "list_sections",
        "get_changelog",
        "submit_answer",
    ]


async def test_a_rejected_draft_goes_back_to_the_model(cache, settings):
    invented = [{"id": "c1", "url": "https://docs.rhesis.ai/docs/nope", "quote": "x" * 20}]
    model = ScriptedModel([[fetch(SCOPE)], [submit(citations=invented)], [submit()]])
    response = await turn(model, cache, settings)

    assert response.route is Route.ANSWERED
    assert "REJECTED" in model.input_text(2)
    assert "was not read this turn" in model.input_text(2)
    assert all("nope" not in c.url for c in response.citations)


async def test_answered_with_no_citations_never_reaches_the_user(cache, settings):
    model = ScriptedModel(
        [[submit(citations=[], claims=[])], [submit(citations=[], claims=[])]], repeat_last=True
    )
    settings = settings.__class__(**{**settings.__dict__, "max_turns": 3})
    response = await turn(model, cache, settings)
    assert response.route is Route.NOT_DOCUMENTED
    assert response.citations == []
    # The third rejected draft uses up the retries; nothing is salvageable, so the run stops.
    assert response.limits_hit == ["grounding_retries"]
    assert len(model.requests) == 3


async def test_a_plain_text_ending_gets_one_nudge(cache, settings):
    model = ScriptedModel([[fetch(SCOPE)], [text("Metric scope is ...")], [submit()]])
    response = await turn(model, cache, settings)

    assert response.route is Route.ANSWERED
    assert NUDGE in model.input_text(2)
    # The unchecked text is never shown.
    assert "Metric scope is ..." not in response.response


async def test_two_plain_text_endings_give_the_fallback(cache, settings):
    model = ScriptedModel(
        [[search("metric scope")], [text("unchecked")], [text("still unchecked")]]
    )
    response = await turn(model, cache, settings)

    assert response.route is Route.NOT_DOCUMENTED
    assert response.limits_hit == ["no_submit"]
    assert response.answer_md == reply("no_submit")
    assert "unchecked" not in response.response
    assert response.related_pages and response.related_pages[0].url == SCOPE


async def test_related_pages_outside_the_index_are_rejected(cache, settings):
    def not_documented(related):
        return submit(
            route="not_documented",
            claims=[],
            citations=[],
            related_pages=related,
            answer_md="Not covered.",
        )

    install = {"title": "Wrong title", "url": "https://docs.rhesis.ai/sdk/installation"}
    made_up = {"title": "Made up", "url": "https://docs.rhesis.ai/docs/made-up"}
    model = ScriptedModel([[not_documented([install, made_up])], [not_documented([install])]])
    response = await turn(model, cache, settings)

    assert "related page https://docs.rhesis.ai/docs/made-up is not in the docs index" in (
        model.input_text(1)
    )
    assert response.route is Route.NOT_DOCUMENTED
    # Titles come from the index, not from the model.
    assert [(p.title, p.url) for p in response.related_pages] == [
        ("SDK Installation & Setup", "https://docs.rhesis.ai/sdk/installation")
    ]


async def test_false_premise_shows_the_correction(cache, settings):
    model = ScriptedModel(
        [
            [fetch(SCOPE)],
            [submit(route="false_premise", premise_correction="There is no max_turns option.")],
        ]
    )
    response = await turn(model, cache, settings)
    assert response.route is Route.FALSE_PREMISE
    assert response.premise_correction == "There is no max_turns option."
    assert response.response.startswith("> **Correction:** There is no max_turns option.")


async def test_response_carries_docs_freshness(cache, settings):
    model = ScriptedModel([[fetch(SCOPE)], [submit()]])
    response = await turn(model, cache, settings)
    assert response.docs_as_of == cache.snapshot.fetched_at
    assert response.docs_stale is False
    assert response.conversation_id and response.answer_id


async def test_out_of_retries_keeps_the_grounded_claims(cache, settings):
    bad_quote = {"id": "c2", "url": SCOPE, "quote": "This sentence is nowhere in the docs."}
    mixed = submit(
        answer_md="Good [c1]. Bad [c2].",
        claims=[
            {"text": "Multi-turn needs the transcript.", "citation_ids": ["c1"]},
            {"text": "Invented.", "citation_ids": ["c2"]},
        ],
        citations=[draft()["citations"][0], bad_quote],
    )
    model = ScriptedModel([[fetch(SCOPE)], [mixed], [mixed], [mixed]])
    response = await turn(model, cache, settings)

    assert response.route is Route.PARTIALLY_ANSWERED
    assert response.limits_hit == ["grounding_retries"]
    assert response.undocumented == ["Invented."]
    assert [c.url.split("#")[0] for c in response.citations] == [SCOPE]
    assert len(model.requests) == 4


async def test_the_backstop_trips_on_an_unchecked_draft(ctx):
    from agents import RunContextWrapper

    from docs_assistant.agents.answerer import grounding_backstop
    from docs_assistant.schemas import AnswerDraft

    unchecked = AnswerDraft(**draft())  # cites a page that was never read
    result = await grounding_backstop.guardrail_function(RunContextWrapper(ctx), None, unchecked)
    assert result.tripwire_triggered
    passed = await grounding_backstop.guardrail_function(RunContextWrapper(ctx), None, "text")
    assert not passed.tripwire_triggered


async def test_the_backstop_enforces_the_clarify_streak(ctx):
    from agents import RunContextWrapper

    from docs_assistant.agents.answerer import grounding_backstop
    from docs_assistant.schemas import AnswerDraft

    clarifying = AnswerDraft(
        **draft(
            route="needs_clarification",
            answer_md="",
            claims=[],
            citations=[],
            clarification={"question": "Where?", "options": ["Web app", "Python SDK"]},
        )
    )
    wrapper = RunContextWrapper(ctx)
    assert not (
        await grounding_backstop.guardrail_function(wrapper, None, clarifying)
    ).tripwire_triggered
    ctx.allow_clarify = False
    assert (
        await grounding_backstop.guardrail_function(wrapper, None, clarifying)
    ).tripwire_triggered

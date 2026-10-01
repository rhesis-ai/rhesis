from docs_assistant.agents.answerer import NUDGE
from docs_assistant.runner import run_turn
from docs_assistant.schemas import Route
from docs_assistant.terminals import text as reply
from tests.mocks import ScriptedModel, fetch, models, search, submit, text

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
    assert "max_turns" in response.limits_hit


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


async def test_not_documented_keeps_only_related_pages_the_index_knows(cache, settings):
    related = [
        {"title": "Wrong title", "url": "https://docs.rhesis.ai/sdk/installation"},
        {"title": "Made up", "url": "https://docs.rhesis.ai/docs/made-up"},
    ]
    model = ScriptedModel(
        [
            [
                submit(
                    route="not_documented",
                    claims=[],
                    citations=[],
                    related_pages=related,
                    answer_md="Not covered.",
                )
            ]
        ]
    )
    response = await turn(model, cache, settings)

    assert response.route is Route.NOT_DOCUMENTED
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

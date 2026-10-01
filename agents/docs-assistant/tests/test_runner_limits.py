from dataclasses import replace

import pytest

from docs_assistant.corpus.cache import DocsUnavailable
from docs_assistant.runner import run_turn
from docs_assistant.schemas import Route
from docs_assistant.terminals import text as reply
from tests.mocks import ScriptedModel, fetch, models, search, submit

SCOPE = "https://docs.rhesis.ai/docs/metrics/metric-scope"


async def test_max_turns_ends_in_the_fallback(cache, settings):
    model = ScriptedModel([[search("metric scope")]], repeat_last=True)
    response = await run_turn(
        "q", cache=cache, models=models(model), settings=replace(settings, max_turns=3)
    )
    assert response.route is Route.NOT_DOCUMENTED
    assert "max_turns" in response.limits_hit
    assert response.answer_md == reply("fallback")
    assert response.related_pages[0].url == SCOPE


async def test_timeout_ends_in_the_fallback(cache, settings):
    model = ScriptedModel([[search("metric scope")], [submit()]], delay=0.2)
    response = await run_turn(
        "q", cache=cache, models=models(model), settings=replace(settings, turn_timeout=0.1)
    )
    assert response.route is Route.NOT_DOCUMENTED
    assert response.limits_hit == ["timeout"]


async def test_token_budget_ends_in_the_fallback(cache, settings):
    model = ScriptedModel([[fetch(SCOPE)], [submit()]], tokens_per_call=5000)
    response = await run_turn(
        "q", cache=cache, models=models(model), settings=replace(settings, token_budget=4000)
    )
    assert response.route is Route.NOT_DOCUMENTED
    assert response.limits_hit == ["token_budget"]
    assert len(model.requests) == 1


async def test_tool_budget_is_reported_with_the_answer(cache, settings):
    not_documented = submit(
        route="not_documented", claims=[], citations=[], answer_md="Not covered."
    )
    model = ScriptedModel([[search("a")], [search("b")], [fetch(SCOPE)], [not_documented]])
    response = await run_turn(
        "q", cache=cache, models=models(model), settings=replace(settings, max_tool_calls=2)
    )
    assert "BUDGET_EXHAUSTED" in model.input_text(3)
    assert response.route is Route.NOT_DOCUMENTED
    assert response.limits_hit == ["tool_budget"]


async def test_no_docs_at_all_raises(cache, site, settings):
    site.down = True
    with pytest.raises(DocsUnavailable):
        await run_turn("q", cache=cache, models=models(), settings=settings)


async def test_a_submit_that_crosses_the_token_budget_still_counts(cache, settings):
    model = ScriptedModel([[fetch(SCOPE)], [submit()]], tokens_per_call=2500)
    response = await run_turn(
        "q", cache=cache, models=models(model), settings=replace(settings, token_budget=4000)
    )
    assert response.route is Route.ANSWERED
    assert response.limits_hit == ["token_budget"]

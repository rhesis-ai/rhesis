"""The critic's veto: re-run once, then drop what is still unsupported."""

from dataclasses import replace

from docs_assistant.agents.critic import critic_input, surrounding_text
from docs_assistant.runner import run_turn
from docs_assistant.schemas import AnswerDraft, Route
from tests.mocks import ScriptedModel, draft, fetch, models, submit, text, verdict

SCOPE = "https://docs.rhesis.ai/docs/metrics/metric-scope"
GOOD = {
    "id": "c1",
    "url": f"{SCOPE}#when-to-use-multi-turn",
    "quote": "Full transcript required — context retention, multi-step threads",
}
ALSO_GOOD = {"id": "c2", "url": SCOPE, "quote": "One `test_type` per test set."}
TWO_CLAIMS = {
    "answer_md": "Multi-turn needs the transcript [c1]. Use one test type per set [c2].",
    "claims": [
        {"text": "Multi-turn metrics need the full transcript.", "citation_ids": ["c1"]},
        {"text": "Each test set allows ten test types.", "citation_ids": ["c2"]},
    ],
    "citations": [GOOD, ALSO_GOOD],
}


async def turn(cache, settings, answer_model, critic_model):
    return await run_turn(
        "q", cache=cache, models=models(answer_model, critic=critic_model), settings=settings
    )


async def test_an_approved_draft_passes_unchanged(cache, settings):
    critic_model = ScriptedModel([[verdict(True)]])
    response = await turn(
        cache, settings, ScriptedModel([[fetch(SCOPE)], [submit()]]), critic_model
    )
    assert response.route is Route.ANSWERED
    assert "critic_veto" not in response.limits_hit
    assert critic_model.requests[0]["tools"] == []
    assert "Claim 1: A claim." in critic_model.input_text(0)


async def test_a_veto_reruns_the_answer_once_with_feedback(cache, settings):
    fixed = {
        **TWO_CLAIMS,
        "answer_md": "Multi-turn needs the transcript [c1].",
        "claims": TWO_CLAIMS["claims"][:1],
        "citations": [GOOD],
    }
    answer_model = ScriptedModel([[fetch(SCOPE)], [submit(**TWO_CLAIMS)], [submit(**fixed)]])
    critic_model = ScriptedModel([[verdict(True, False)], [verdict(True)]])
    response = await turn(cache, settings, answer_model, critic_model)

    assert response.route is Route.ANSWERED
    assert "critic_veto" in response.limits_hit
    sent = answer_model.input_text(2)
    assert "Each test set allows ten test types." in sent and "not in the text" in sent
    assert len(critic_model.requests) == 2


async def test_a_second_veto_drops_the_claim_and_downgrades(cache, settings):
    answer_model = ScriptedModel([[fetch(SCOPE)], [submit(**TWO_CLAIMS)], [submit(**TWO_CLAIMS)]])
    critic_model = ScriptedModel([[verdict(True, False)], [verdict(True, False)]])
    response = await turn(cache, settings, answer_model, critic_model)

    assert response.route is Route.PARTIALLY_ANSWERED
    assert response.undocumented == ["Each test set allows ten test types."]
    assert [c.url for c in response.citations] == [GOOD["url"]]
    assert "ten test types" not in response.answer_md


async def test_nothing_supported_left_ends_not_documented(cache, settings):
    answer_model = ScriptedModel([[fetch(SCOPE)], [submit()], [submit()]])
    critic_model = ScriptedModel([[verdict(False)], [verdict(False)]])
    response = await turn(cache, settings, answer_model, critic_model)
    assert response.route is Route.NOT_DOCUMENTED
    assert response.citations == []


async def test_the_critic_skips_drafts_without_claims(cache, settings):
    not_documented = submit(route="not_documented", claims=[], citations=[], answer_md="No.")
    critic_model = ScriptedModel([])
    response = await turn(cache, settings, ScriptedModel([[not_documented]]), critic_model)
    assert response.route is Route.NOT_DOCUMENTED
    assert critic_model.requests == []


async def test_the_flag_turns_the_critic_off(cache, settings):
    critic_model = ScriptedModel([])
    answer_model = ScriptedModel([[fetch(SCOPE)], [submit()]])
    response = await turn(cache, replace(settings, critic=False), answer_model, critic_model)
    assert response.route is Route.ANSWERED
    assert critic_model.requests == []


async def test_a_broken_critic_keeps_the_checked_draft(cache, settings):
    critic_model = ScriptedModel([[text("not json")]])
    response = await turn(
        cache, settings, ScriptedModel([[fetch(SCOPE)], [submit()]]), critic_model
    )
    assert response.route is Route.ANSWERED
    assert "critic_unavailable" in response.limits_hit


def test_critic_input_shows_each_quote_in_its_context(snapshot):
    ledger = {SCOPE: snapshot.page(SCOPE)}
    sent = critic_input(AnswerDraft(**draft(**TWO_CLAIMS)), ledger)
    assert "Claim 2: Each test set allows ten test types." in sent
    assert 'Quote: "One `test_type` per test set."' in sent
    assert "Requirements listed on each test set" in sent  # the text right after the quote


def test_surrounding_text_falls_back_to_normalized_matching():
    body = "Intro. The **metric scope** decides   where it runs. Outro."
    assert "metric scope decides where it runs" in surrounding_text(
        body, "the metric scope decides where it runs", chars=5
    )
    assert surrounding_text(body, "not there at all") == ""

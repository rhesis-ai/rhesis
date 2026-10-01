"""Messages with several questions: parallel parts, one merged reply, the turn-route rule."""

from dataclasses import replace

import pytest

from docs_assistant.compose import turn_route
from docs_assistant.runner import run_turn
from docs_assistant.schemas import Route
from tests.mocks import ScriptedModel, fetch, models, submit, triage, triage_part

INSTALL = "https://docs.rhesis.ai/sdk/installation"
DOCKER = "https://docs.rhesis.ai/self-hosting/docker-compose"
INSTALL_ANSWER = {
    "answer_md": "Install it with pip [c1].",
    "citations": [
        {"id": "c1", "url": INSTALL, "quote": "The Rhesis Python SDK generates test sets"}
    ],
}
DOCKER_ANSWER = {
    "answer_md": "Use Docker Compose [c1].",
    "citations": [{"id": "c1", "url": DOCKER, "quote": "Deploy Rhesis on your own infrastructure"}],
}


class ByQuestion(ScriptedModel):
    """An answer model that replies per question, so parallel parts don't share one script."""

    def __init__(self, scripts):
        super().__init__([])
        self.scripts = {q: list(s) for q, s in scripts.items()}

    async def get_response(self, system_instructions, input, *args, **kwargs):
        first = input if isinstance(input, str) else str(input[0].get("content"))
        question = next(q for q in self.scripts if q in first)
        self.script = [self.scripts[question].pop(0)]
        return await super().get_response(system_instructions, input, *args, **kwargs)


async def turn(cache, settings, decision, answer_model):
    return await run_turn(
        "m",
        cache=cache,
        models=models(answer_model, ScriptedModel([[decision]])),
        settings=settings,
    )


async def test_two_docs_parts_get_one_section_each(cache, settings):
    decision = triage(
        triage_part("How do I install the SDK?", surface="sdk"),
        triage_part("How do I self-host with Docker?", surface="self_hosting"),
    )
    answer_model = ByQuestion(
        {
            "install the SDK": [[fetch(INSTALL)], [submit(**INSTALL_ANSWER)]],
            "self-host": [[fetch(DOCKER)], [submit(**DOCKER_ANSWER)]],
        }
    )
    response = await turn(cache, settings, decision, answer_model)

    assert response.route is Route.ANSWERED
    assert response.surface == "both"
    assert [p.route for p in response.parts] == [Route.ANSWERED, Route.ANSWERED]
    assert "### How do I install the SDK?" in response.response
    assert "### How do I self-host with Docker?" in response.response
    # Sources are numbered across the turn: the second part's [c1] is source 2.
    assert f"[\\[1\\]]({INSTALL}" in response.response
    assert f"[\\[2\\]]({DOCKER}" in response.response
    assert response.response.count("**Sources**") == 1
    assert [c.url.split("#")[0] for c in response.citations] == [INSTALL, DOCKER]


async def test_a_docs_part_next_to_an_off_topic_part_is_partial(cache, settings):
    decision = triage(
        triage_part("How do I install the SDK?"), triage_part("Write a poem", "out_of_scope")
    )
    answer_model = ScriptedModel([[fetch(INSTALL)], [submit(**INSTALL_ANSWER)]])
    response = await turn(cache, settings, decision, answer_model)

    assert response.route is Route.PARTIALLY_ANSWERED
    assert [p.route for p in response.parts] == [Route.ANSWERED, Route.OUT_OF_SCOPE]
    assert "outside what I can help with" in response.response


async def test_a_greeting_next_to_a_question_is_dropped(cache, settings):
    decision = triage(triage_part("hi", "smalltalk"), triage_part("How do I install the SDK?"))
    answer_model = ScriptedModel([[fetch(INSTALL)], [submit(**INSTALL_ANSWER)]])
    response = await turn(cache, settings, decision, answer_model)
    assert response.route is Route.ANSWERED
    assert len(response.parts) == 1
    assert "###" not in response.response


async def test_parts_share_one_token_budget(cache, settings):
    decision = triage(triage_part("q one"), triage_part("q two"))
    answer_model = ScriptedModel([[fetch(INSTALL)]], repeat_last=True, tokens_per_call=400)
    response = await turn(cache, replace(settings, token_budget=1000), decision, answer_model)
    assert "token_budget" in response.limits_hit
    # Alone, each part would make 3 calls before passing 1000 tokens. Shared, the turn stops
    # after the third call in total (a fourth may already be in flight).
    assert len(answer_model.requests) <= 4


@pytest.mark.parametrize(
    ("routes", "expected"),
    [
        ([Route.ANSWERED, Route.ANSWERED], Route.ANSWERED),
        ([Route.ANSWERED, Route.NOT_DOCUMENTED], Route.PARTIALLY_ANSWERED),
        ([Route.PARTIALLY_ANSWERED, Route.OUT_OF_SCOPE], Route.PARTIALLY_ANSWERED),
        ([Route.NOT_DOCUMENTED, Route.FALSE_PREMISE], Route.FALSE_PREMISE),
        ([Route.NOT_DOCUMENTED, Route.ACCOUNT_OR_SUPPORT], Route.ACCOUNT_OR_SUPPORT),
        ([Route.ANSWERED, Route.UNSAFE_OR_INJECTION], Route.UNSAFE_OR_INJECTION),
    ],
)
def test_turn_route_rule(routes, expected):
    assert turn_route(routes) is expected

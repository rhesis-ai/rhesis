import pytest

from docs_assistant.grounding import validate
from docs_assistant.schemas import AnswerDraft
from tests.mocks import draft

SCOPE = "https://docs.rhesis.ai/docs/metrics/metric-scope"


@pytest.fixture
def ledger(snapshot):
    return {
        SCOPE: snapshot.page(SCOPE),
        "https://docs.rhesis.ai/sdk/metrics": snapshot.page("sdk/metrics"),
    }


def check(ledger, **overrides):
    return validate(AnswerDraft(**draft(**overrides)), ledger)


def test_a_grounded_answer_passes(ledger):
    assert check(ledger) == []


def test_anchor_and_md_forms_of_a_read_page_pass(ledger):
    citations = [{"id": "c1", "url": f"{SCOPE}.md#planning-checklist", "quote": "x" * 20}]
    assert check(ledger, citations=citations) == []


def test_invented_url_is_rejected(ledger):
    citations = [{"id": "c1", "url": "https://docs.rhesis.ai/docs/made-up-page", "quote": "x" * 20}]
    problems = check(ledger, citations=citations)
    assert problems == [
        "citation c1: https://docs.rhesis.ai/docs/made-up-page was not read this turn; "
        "call fetch_page on it first or remove the citation"
    ]


def test_a_page_only_seen_in_search_is_rejected(snapshot, ledger):
    # sdk/installation exists in the corpus but was never fetched this turn.
    citations = [{"id": "c1", "url": "https://docs.rhesis.ai/sdk/installation", "quote": "x" * 20}]
    assert any("was not read this turn" in p for p in check(ledger, citations=citations))


def test_answered_with_no_citations_is_rejected(ledger):
    problems = check(ledger, citations=[], claims=[])
    assert "answered needs claims with citations" in problems


def test_claims_must_cite_existing_ids(ledger):
    claims = [{"text": "a", "citation_ids": []}, {"text": "b", "citation_ids": ["c9"]}]
    problems = check(ledger, claims=claims)
    assert "claim 1 has no citation" in problems
    assert "claim 2 cites c9, which is not in citations" in problems


def test_duplicate_citation_ids_are_rejected(ledger):
    cite = {"id": "c1", "url": SCOPE, "quote": "x" * 20}
    assert "citation id c1 is used twice" in check(ledger, citations=[cite, cite])


def test_answered_must_not_list_gaps(ledger):
    problems = check(ledger, undocumented=["pricing"])
    assert any("use partially_answered" in p for p in problems)


def test_partially_answered_must_list_gaps(ledger):
    problems = check(ledger, route="partially_answered")
    assert "partially_answered must list what the docs don't cover" in problems
    assert check(ledger, route="partially_answered", undocumented=["pricing"]) == []


def test_not_documented_must_not_make_claims(ledger):
    assert check(ledger, route="not_documented") == [
        "not_documented must not make claims or cite pages; use related_pages"
    ]
    assert check(ledger, route="not_documented", claims=[], citations=[]) == []


def test_false_premise_needs_a_correction_and_a_citation(ledger):
    problems = check(ledger, route="false_premise")
    assert problems == ["false_premise needs premise_correction"]
    assert check(ledger, route="false_premise", premise_correction="There is no such flag.") == []
    problems = check(
        ledger, route="false_premise", premise_correction="No.", claims=[], citations=[]
    )
    assert problems == ["false_premise needs a citation showing the premise is wrong"]

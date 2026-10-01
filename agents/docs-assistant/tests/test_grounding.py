import pytest

from docs_assistant.grounding import salvage, validate
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
    quote = "metric_scope on every metric (copy from list_metrics when reusing)"
    citations = [{"id": "c1", "url": f"{SCOPE}.md#planning-checklist", "quote": quote}]
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
    assert check(ledger, route="not_documented", claims=[], citations=[], answer_md="No.") == []


def test_false_premise_needs_a_correction_and_a_citation(ledger):
    problems = check(ledger, route="false_premise")
    assert problems == ["false_premise needs premise_correction"]
    assert check(ledger, route="false_premise", premise_correction="There is no such flag.") == []
    problems = check(
        ledger,
        route="false_premise",
        premise_correction="No.",
        claims=[],
        citations=[],
        answer_md="No such flag.",
    )
    assert problems == ["false_premise needs a citation showing the premise is wrong"]


def test_markers_in_the_answer_must_be_known_citations(ledger):
    problems = check(ledger, answer_md="Scope decides it [c1]. Also true [c9] and [c1, c7].")
    assert problems == [
        "answer_md uses [c9], which is not in citations; add that citation or remove the marker",
        "answer_md uses [c7], which is not in citations; add that citation or remove the marker",
    ]


def test_a_marker_with_no_citations_at_all_is_rejected(ledger):
    problems = check(ledger, route="not_documented", claims=[], citations=[])
    assert problems == [
        "answer_md uses [c1], which is not in citations; add that citation or remove the marker"
    ]


def test_brackets_that_are_not_markers_are_ignored(ledger):
    answer_md = (
        "Uses [c1]. See [the guide](https://docs.rhesis.ai/sdk/metrics), version [0.13.0], "
        "a [Note] box, `list[str]` and `values[c2]` in code, and\n\n```python\nx = y[c3]\n```"
    )
    adapted = [{"code": "x = y[c3]", "source_url": SCOPE}]
    assert check(ledger, answer_md=answer_md, adapted_code=adapted) == []


# ── rules 2, 3, 6, 7, 8 ──────────────────────────────────────────────────────────────────

METRICS = "https://docs.rhesis.ai/sdk/metrics"
QUOTE = "Scopes are additive: including more values makes the metric eligible in more contexts."


def cite(url=METRICS, quote=QUOTE, id="c1"):
    return {"id": id, "url": url, "quote": quote}


def test_a_bad_anchor_is_rejected(ledger):
    problems = check(ledger, citations=[cite(f"{METRICS}#no-such-heading")])
    assert problems == [
        f"citation c1: #no-such-heading is not a heading on {METRICS}; use an anchor from the "
        "headings fetch_page listed, or cite the page without one"
    ]


def test_a_real_anchor_passes(ledger):
    assert check(ledger, citations=[cite(f"{METRICS}#metric-scopes")]) == []


def test_a_quote_not_on_the_page_is_rejected(ledger):
    problems = check(ledger, citations=[cite(quote="Scopes are multiplied across every context.")])
    assert problems == [
        f"citation c1: the quote is not on {METRICS} word for word; copy the exact sentence "
        "from the page"
    ]


def test_quotes_match_across_markdown_case_and_whitespace(ledger):
    quote = "every METRIC has a metric_scope   that controls\nwhere and when it runs"
    assert check(ledger, citations=[cite(quote=quote)]) == []


def test_a_short_quote_is_rejected(ledger):
    problems = check(ledger, citations=[cite(quote="Scopes are")])
    assert problems == [
        "citation c1: the quote must be at least 20 characters copied from the page"
    ]


def test_code_copied_from_a_page_passes(ledger):
    answer_md = "Restrict it [c1]:\n\n```python\nmetric_scope=[MetricScope.SINGLE_TURN],\n```"
    assert check(ledger, answer_md=answer_md, citations=[cite()]) == []


def test_invented_code_is_rejected_unless_adapted(ledger):
    answer_md = "Do this [c1]:\n\n```python\nmetric = NumericJudge(name='mine')\n```"
    problems = check(ledger, answer_md=answer_md, citations=[cite()])
    assert problems and problems[0].startswith("code block 1 in answer_md is not copied")

    adapted = [{"code": "metric = NumericJudge(name='mine')", "source_url": METRICS}]
    assert check(ledger, answer_md=answer_md, citations=[cite()], adapted_code=adapted) == []


def test_adapted_code_must_name_a_page_that_was_read(ledger):
    answer_md = "Do this [c1]:\n\n```python\nmetric = NumericJudge(name='mine')\n```"
    adapted = [{"code": "metric = NumericJudge(name='mine')", "source_url": "sdk/installation"}]
    problems = check(ledger, answer_md=answer_md, citations=[cite()], adapted_code=adapted)
    assert problems and problems[0].startswith("code block 1")


def test_links_must_be_known_pages_or_on_a_read_page(ledger):
    answer_md = (
        "See [scope](/docs/metrics/metric-scope) "
        "and [trace metrics](/docs/metrics/trace-metrics) [c1]."
    )
    assert check(ledger, answer_md=answer_md, citations=[cite()]) == [
        "link /docs/metrics/trace-metrics is not a docs page; link only pages that exist"
    ]


def test_with_the_snapshot_indexed_pages_count_as_known(ledger, snapshot):
    answer_md = "See [install](https://docs.rhesis.ai/sdk/installation) [c1]."
    draft_ = AnswerDraft(**draft(answer_md=answer_md, citations=[cite()]))
    assert validate(draft_, ledger, snapshot) == []


def test_an_external_link_not_on_any_read_page_is_rejected(ledger):
    answer_md = "See [this](https://example.com/guide) [c1]."
    assert check(ledger, answer_md=answer_md, citations=[cite()]) == [
        "link https://example.com/guide does not appear on any page you read; remove it"
    ]


def test_related_pages_must_be_in_the_index(ledger, snapshot):
    related = [{"title": "x", "url": "https://docs.rhesis.ai/docs/nope"}]
    draft_ = AnswerDraft(
        **draft(
            route="not_documented", answer_md="No.", claims=[], citations=[], related_pages=related
        )
    )
    assert validate(draft_, ledger, snapshot) == [
        "related page https://docs.rhesis.ai/docs/nope is not in the docs index; pick pages "
        "from search or list_sections"
    ]


# ── salvage ──────────────────────────────────────────────────────────────────────────────


def test_salvage_keeps_only_grounded_claims(ledger):
    bad = cite(quote="This sentence is nowhere in the docs at all.", id="c2")
    draft_ = AnswerDraft(
        **draft(
            answer_md="Good [c1]. Bad [c2].",
            claims=[
                {"text": "Scopes add up.", "citation_ids": ["c1"]},
                {"text": "Scopes multiply.", "citation_ids": ["c2"]},
            ],
            citations=[cite(), bad],
        )
    )
    kept = salvage(draft_, ledger)
    assert kept.route == "partially_answered"
    assert kept.answer_md == "- Scopes add up. [c1]"
    assert [c.id for c in kept.citations] == ["c1"]
    assert kept.undocumented == ["Scopes multiply."]


def test_salvage_gives_up_when_nothing_is_grounded(ledger):
    bad = cite(quote="This sentence is nowhere in the docs at all.")
    assert salvage(AnswerDraft(**draft(citations=[bad])), ledger) is None


def test_a_conflict_must_cite_both_sides(ledger):
    one_side = [{"summary": "Pages disagree.", "citation_ids": ["c1"]}]
    assert check(ledger, conflicts=one_side) == [
        "conflict 1 must cite the pages on both sides (two citations)"
    ]
    unknown = [{"summary": "Pages disagree.", "citation_ids": ["c1", "c9"]}]
    assert check(ledger, conflicts=unknown) == ["conflict 1 cites c9, which is not in citations"]

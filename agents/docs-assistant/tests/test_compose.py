from datetime import datetime, timezone

from docs_assistant.compose import (
    PartOutcome,
    citations_for,
    footer,
    number_markers,
    related_pages_for,
    render,
    render_clarification,
)
from docs_assistant.schemas import AnswerDraft, Clarification, RelatedPage, Route
from tests.mocks import draft

SCOPE = "https://docs.rhesis.ai/docs/metrics/metric-scope"
METRICS = "https://docs.rhesis.ai/sdk/metrics"


def _draft(answer_md, citations):
    return AnswerDraft(**draft(answer_md=answer_md, citations=citations))


def test_citations_are_unique_and_titled_from_the_page(snapshot):
    cites = [
        {"id": "c1", "url": f"{SCOPE}#planning-checklist", "quote": "q" * 20},
        {"id": "c2", "url": f"{SCOPE}.md#planning-checklist", "quote": "q" * 20},
        {"id": "c3", "url": METRICS, "quote": "q" * 20},
    ]
    result = citations_for(_draft("a", cites), snapshot, {})
    assert [(c.title, c.url, c.heading) for c in result] == [
        ("Metric scope", f"{SCOPE}#planning-checklist", "Planning checklist"),
        ("Overview", METRICS, None),
    ]


def test_markers_become_numbered_links(snapshot):
    cites = [
        {"id": "c1", "url": SCOPE, "quote": "q" * 20},
        {"id": "c2", "url": METRICS, "quote": "q" * 20},
    ]
    d = _draft("One [c1]. Two [c1, c2]. Code `list[str]` and [a link](x) stay.", cites)
    out = number_markers(d, citations_for(d, snapshot, {}))
    assert out == (
        f"One [\\[1\\]]({SCOPE}). Two [\\[1\\]]({SCOPE})[\\[2\\]]({METRICS}). "
        "Code `list[str]` and [a link](x) stay."
    )


def test_render_lists_gaps_sources_and_related(snapshot):
    d = AnswerDraft(
        **draft(
            route="partially_answered",
            undocumented=["pricing"],
            related_pages=[{"title": "Overview", "url": METRICS}],
        )
    )

    outcome = PartOutcome("q", Route.PARTIALLY_ANSWERED, draft=d)
    text = render([outcome], citations_for(d, snapshot, {}), related_pages_for(d, snapshot))
    assert "**Not covered in the docs:**\n- pricing" in text
    assert "**Sources**\n- [Metric scope › When to use" in text
    assert f"**Related pages**\n- [Overview]({METRICS})" in text


# ── trust signals ────────────────────────────────────────────────────────────────────────

AS_OF = datetime(2026, 10, 1, 9, 30, tzinfo=timezone.utc)
GOOD_QUOTE = "Full transcript required — context retention, multi-step threads"


def _rendered(snapshot, language="en", **overrides):
    d = AnswerDraft(**draft(**overrides))
    outcome = PartOutcome("q", Route(d.route), draft=d)
    citations = citations_for(d, snapshot, {})
    return render([outcome], citations, [], language=language, docs_as_of=AS_OF)


def test_every_answer_ends_with_when_the_docs_were_fetched(snapshot):
    assert _rendered(snapshot).endswith("_Docs as of 2026-10-01 09:30 UTC._")
    assert _rendered(snapshot, "de").endswith("_Stand der Doku: 2026-10-01 09:30 UTC._")


def test_stale_docs_say_so():
    assert footer(AS_OF, True, "en") == (
        "_Docs as of 2026-10-01 09:30 UTC; the live site didn't respond, so they may be out "
        "of date._"
    )


def test_conflicts_become_a_heads_up_with_both_sources(snapshot):
    citations = [
        {"id": "c1", "url": SCOPE, "quote": GOOD_QUOTE},
        {"id": "c2", "url": METRICS, "quote": "Scopes are additive"},
    ]
    conflicts = [
        {"summary": "The two pages list different defaults.", "citation_ids": ["c1", "c2"]}
    ]
    text = _rendered(snapshot, citations=citations, conflicts=conflicts)
    assert (
        f"> **Heads-up:** The two pages list different defaults. [\\[1\\]]({SCOPE})"
        f"[\\[2\\]]({METRICS})"
    ) in text


def test_adapted_code_gets_a_note(snapshot):
    d = AnswerDraft(**draft())
    page = RelatedPage(title="Overview", url=METRICS)
    outcome = PartOutcome("q", Route.ANSWERED, draft=d, adapted=[page])
    text = render([outcome], citations_for(d, snapshot, {}), [])
    assert f"_Adapted from [Overview]({METRICS}); not copied verbatim._" in text


def test_clarifying_options_are_numbered():
    text = render_clarification(Clarification(question="Where?", options=["UI", "SDK"]), "de")
    assert text == (
        "Where?\n\n1. UI\n2. SDK\n\n_Antworte mit einer Nummer oder in deinen eigenen Worten._"
    )

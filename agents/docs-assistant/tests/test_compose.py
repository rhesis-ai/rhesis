from docs_assistant.compose import citations_for, number_markers, related_pages_for, render
from docs_assistant.schemas import AnswerDraft
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

    text = render(d, citations_for(d, snapshot, {}), related_pages_for(d, snapshot))
    assert "**Not covered in the docs:**\n- pricing" in text
    assert "**Sources**\n- [Metric scope › When to use" in text
    assert f"**Related pages**\n- [Overview]({METRICS})" in text

from docs_assistant.corpus.parser import (
    build_page,
    canonical_url,
    parse_llms_full,
    parse_llms_txt,
    parse_page_markdown,
    slugify,
    split_anchor,
)
from tests.conftest import EXTRA_PAGES, LLMS_FULL, LLMS_TXT


def test_slugify_matches_the_ids_on_the_html_site():
    # Real ids from https://docs.rhesis.ai/docs/metrics/metric-scope
    assert slugify('When to use `["Single-Turn"]`') == "when-to-use-single-turn"
    assert slugify('When to use `["Multi-Turn"]`') == "when-to-use-multi-turn"
    assert slugify("When to use both") == "when-to-use-both"
    assert slugify("Planning checklist") == "planning-checklist"


def test_slugify_handles_links_versions_and_underscores():
    assert slugify("See [the SDK](/sdk) docs") == "see-the-sdk-docs"
    assert slugify("[0.13.0] - 2026-08-20") == "0130---2026-08-20"
    assert slugify("Jinja2 with `jsonpath()`") == "jinja2-with-jsonpath"
    assert slugify("The `max_turns` option") == "the-max_turns-option"


def test_canonical_url_accepts_every_form():
    expected = "https://docs.rhesis.ai/docs/metrics/metric-scope"
    for form in [
        "https://docs.rhesis.ai/docs/metrics/metric-scope",
        "https://docs.rhesis.ai/docs/metrics/metric-scope.md",
        "https://docs.rhesis.ai/docs/metrics/metric-scope/",
        "https://docs.rhesis.ai/docs/metrics/metric-scope#when-to-use-both",
        "https://docs.rhesis.ai/api/md/docs/metrics/metric-scope",
        "http://localhost:8765/docs/metrics/metric-scope",
        "/docs/metrics/metric-scope",
        "docs/metrics/metric-scope",
    ]:
        assert canonical_url(form) == expected, form


def test_split_anchor_keeps_the_anchor():
    assert split_anchor("/sdk/metrics.md#metric-scopes") == (
        "https://docs.rhesis.ai/sdk/metrics",
        "metric-scopes",
    )
    assert split_anchor("sdk/metrics") == ("https://docs.rhesis.ai/sdk/metrics", None)


def test_parse_llms_full_reads_every_page():
    pages = {p.path: p for p in parse_llms_full(LLMS_FULL)}
    assert set(pages) == {
        "docs/metrics/metric-scope",
        "docs/endpoints/response-mapping",
        "docs/endpoints/sdk-endpoints",
        "docs/api-tokens",
        "sdk/installation",
        "sdk/metrics",
        "self-hosting/docker-compose",
        "changelog",
    }
    scope = pages["docs/metrics/metric-scope"]
    assert scope.title == "Metric scope"
    assert scope.url == "https://docs.rhesis.ai/docs/metrics/metric-scope"
    assert {"when-to-use-single-turn", "when-to-use-multi-turn", "planning-checklist"} <= (
        scope.anchors
    )
    assert pages["self-hosting/docker-compose"].section == "self_hosting"


def test_sections_start_with_the_intro_and_keep_their_heading_line():
    scope = parse_page_markdown(EXTRA_PAGES["glossary/hallucination"])
    assert scope.sections[0].anchor == ""
    assert scope.sections[0].heading == "Hallucination"
    page = {p.path: p for p in parse_llms_full(LLMS_FULL)}["docs/metrics/metric-scope"]
    multi = page.sections[page.find_section("when-to-use-multi-turn")]
    assert multi.text.startswith('## When to use `["Multi-Turn"]`')
    assert "context retention" in multi.text


def test_headings_inside_code_fences_are_not_sections():
    body = "# T\n\nIntro\n\n```md\n## Not a heading\n```\n\n## Real\n\nText\n\n## Real\n\nMore"
    page = build_page("https://docs.rhesis.ai/x", "T", body)
    assert [s.anchor for s in page.sections] == ["", "real", "real-1"]
    assert page.code_blocks == ["## Not a heading"]


def test_links_are_canonical_and_keep_anchors():
    body = (
        "[Scope](/glossary/metric-scope) [Plan](https://docs.rhesis.ai/docs/architect/planning#x) "
        "[Ext](https://example.com/a) [Again](/glossary/metric-scope)"
    )
    page = build_page("https://docs.rhesis.ai/x", "T", body)
    assert [link.url for link in page.links] == [
        "https://docs.rhesis.ai/glossary/metric-scope",
        "https://docs.rhesis.ai/docs/architect/planning#x",
    ]


def test_parse_llms_txt_keeps_docs_links_once_with_their_section():
    entries = {e.url: e for e in parse_llms_txt(LLMS_TXT)}
    # metric-scope appears under "Agent reference" and "Docs"; it is kept once.
    assert len(entries) == 10
    assert entries["https://docs.rhesis.ai/glossary/hallucination"].section == "glossary"
    assert entries["https://docs.rhesis.ai/changelog"].section == "changelog"
    assert entries["https://docs.rhesis.ai/sdk/installation"].description.startswith("Install")
    assert all(url.startswith("https://docs.rhesis.ai/") for url in entries)

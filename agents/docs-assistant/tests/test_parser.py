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
    # Real ids from https://docs.rhesis.ai/docs/metrics/targets
    assert slugify("Which tests a metric runs on") == "which-tests-a-metric-runs-on"
    assert slugify("Default target") == "default-target"
    assert slugify("Choices") == "choices"
    assert slugify("Setting a target") == "setting-a-target"


def test_slugify_handles_links_versions_and_underscores():
    assert slugify("See [the SDK](/sdk) docs") == "see-the-sdk-docs"
    assert slugify("[0.13.0] - 2026-08-20") == "0130---2026-08-20"
    assert slugify("Jinja2 with `jsonpath()`") == "jinja2-with-jsonpath"
    assert slugify("The `max_turns` option") == "the-max_turns-option"


def test_canonical_url_accepts_every_form():
    expected = "https://docs.rhesis.ai/docs/metrics/targets"
    for form in [
        "https://docs.rhesis.ai/docs/metrics/targets",
        "https://docs.rhesis.ai/docs/metrics/targets.md",
        "https://docs.rhesis.ai/docs/metrics/targets/",
        "https://docs.rhesis.ai/docs/metrics/targets#choices",
        "https://docs.rhesis.ai/api/md/docs/metrics/targets",
        "http://localhost:8765/docs/metrics/targets",
        "/docs/metrics/targets",
        "docs/metrics/targets",
    ]:
        assert canonical_url(form) == expected, form


def test_split_anchor_keeps_the_anchor():
    assert split_anchor("/sdk/metrics.md#targets") == (
        "https://docs.rhesis.ai/sdk/metrics",
        "targets",
    )
    assert split_anchor("sdk/metrics") == ("https://docs.rhesis.ai/sdk/metrics", None)


def test_parse_llms_full_reads_every_page():
    pages = {p.path: p for p in parse_llms_full(LLMS_FULL)}
    assert set(pages) == {
        "docs/metrics/targets",
        "docs/endpoints/response-mapping",
        "docs/endpoints/sdk-endpoints",
        "docs/api-tokens",
        "sdk/installation",
        "sdk/metrics",
        "self-hosting/docker-compose",
        "changelog",
    }
    scope = pages["docs/metrics/targets"]
    assert scope.title == "Metric Targets"
    assert scope.url == "https://docs.rhesis.ai/docs/metrics/targets"
    assert {"default-target", "which-tests-a-metric-runs-on", "setting-a-target"} <= (scope.anchors)
    assert pages["self-hosting/docker-compose"].section == "self_hosting"


def test_sections_start_with_the_intro_and_keep_their_heading_line():
    scope = parse_page_markdown(EXTRA_PAGES["glossary/hallucination"])
    assert scope.sections[0].anchor == ""
    assert scope.sections[0].heading == "Hallucination"
    page = {p.path: p for p in parse_llms_full(LLMS_FULL)}["docs/metrics/targets"]
    multi = page.sections[page.find_section("which-tests-a-metric-runs-on")]
    assert multi.text.startswith("## Which tests a metric runs on")
    assert "never runs on single-turn tests" in multi.text


def test_headings_inside_code_fences_are_not_sections():
    body = "# T\n\nIntro\n\n```md\n## Not a heading\n```\n\n## Real\n\nText\n\n## Real\n\nMore"
    page = build_page("https://docs.rhesis.ai/x", "T", body)
    assert [s.anchor for s in page.sections] == ["", "real", "real-1"]
    assert page.code_blocks == ["## Not a heading"]


def test_links_are_canonical_and_keep_anchors():
    body = (
        "[Term](/glossary/metric-target) [Plan](https://docs.rhesis.ai/docs/architect/planning#x) "
        "[Ext](https://example.com/a) [Again](/glossary/metric-target)"
    )
    page = build_page("https://docs.rhesis.ai/x", "T", body)
    assert [link.url for link in page.links] == [
        "https://docs.rhesis.ai/glossary/metric-target",
        "https://docs.rhesis.ai/docs/architect/planning#x",
    ]


def test_parse_llms_txt_keeps_docs_links_once_with_their_section():
    entries = {e.url: e for e in parse_llms_txt(LLMS_TXT)}
    # The targets page appears under "Agent reference" and "Docs"; it is kept once.
    assert len(entries) == 10
    assert entries["https://docs.rhesis.ai/glossary/hallucination"].section == "glossary"
    assert entries["https://docs.rhesis.ai/changelog"].section == "changelog"
    assert entries["https://docs.rhesis.ai/sdk/installation"].description.startswith("Install")
    assert all(url.startswith("https://docs.rhesis.ai/") for url in entries)

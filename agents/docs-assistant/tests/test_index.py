import pytest

from docs_assistant.corpus.index import SearchIndex, tokenize
from docs_assistant.corpus.parser import IndexEntry, build_page

TOP_HITS = [
    ("how do I install the SDK", "sdk/installation", "installation"),
    ("extract values from my API response with JSONPath", "docs/endpoints/response-mapping", ""),
    (
        "register a python function as an endpoint with a decorator",
        "docs/endpoints/sdk-endpoints",
        "",
    ),
    ("generate an API token", "docs/api-tokens", ""),
    ("deploy with docker compose", "self-hosting/docker-compose", ""),
    ("RHESIS_API_KEY", "sdk/installation", "configure-the-sdk"),
    ("hallucination", "glossary/hallucination", ""),
    ("prompt injection", "glossary/prompt-injection", ""),
    ("MetricSynthesizer", "sdk/metrics", "generate-and-improve-metrics-with-metricsynthesizer"),
    ("backup the database", "self-hosting/docker-compose", "database-backup"),
]


@pytest.mark.parametrize(("query", "path", "anchor"), TOP_HITS)
def test_top_hit(snapshot, query, path, anchor):
    hit = snapshot.index.search(query, k=1)[0]
    assert (hit.url, hit.anchor) == (f"https://docs.rhesis.ai/{path}", anchor)


def test_a_question_spanning_sections_still_finds_the_page(snapshot):
    hits = snapshot.index.search("difference between single-turn and multi-turn metrics", k=3)
    assert "https://docs.rhesis.ai/docs/metrics/metric-scope" in [h.url for h in hits]


def test_tokenize_splits_code_names_and_drops_stopwords():
    assert tokenize("How do I use MultiTurnMetric?") == [
        "use",
        "multiturnmetric",
        "multi",
        "turn",
        "metric",
    ]
    assert tokenize("max_turns") == ["max_turns", "max", "turns"]
    assert tokenize("Single-Turn") == ["singleturn", "single", "turn"]


def test_section_filter_and_one_hit_per_section(snapshot):
    hits = snapshot.index.search("install", section="sdk", k=10)
    assert hits and all(h.section == "sdk" for h in hits)
    assert len({(h.url, h.anchor) for h in hits}) == len(hits)
    assert snapshot.index.search("   ") == []


def test_snippets_are_short_and_centred_on_the_match(snapshot):
    hit = snapshot.index.search("database backup", k=1)[0]
    assert len(hit.snippet) <= 302
    assert "backup" in hit.snippet.lower()


def _page(path, title, body):
    return build_page(f"https://docs.rhesis.ai/{path}", title, body)


def test_contributor_docs_rank_below_user_docs_unless_asked_for():
    body = "# Worker\n\nThe worker runs test jobs."
    index = SearchIndex(
        [_page("contribute/worker", "Worker", body), _page("docs/worker", "Worker", body)], []
    )
    user_first = index.search("worker runs test jobs")
    assert user_first[0].url.endswith("docs/worker")
    assert user_first[1].score == pytest.approx(user_first[0].score * 0.6, rel=1e-2)
    asked = index.search("contributing: worker runs test jobs")
    assert asked[0].score == pytest.approx(asked[1].score)


def test_index_only_entries_are_searchable_by_description():
    entry = IndexEntry(
        "Ground Truth",
        "https://docs.rhesis.ai/glossary/ground-truth",
        "Reference answers.",
        "glossary",
    )
    hits = SearchIndex([], [entry]).search("reference answers")
    assert hits[0].url == entry.url

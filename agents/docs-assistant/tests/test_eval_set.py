import re

from docs_assistant.schemas import Route
from examples.run_evals import RowResult, load_rows, page_recall, route_ok, summarize


def test_eval_rows_are_valid():
    rows = load_rows()
    assert len(rows) == 10
    assert len({r["id"] for r in rows}) == len(rows)
    for row in rows:
        assert row["question"].strip()
        Route(row["expected_route"])
        for group in row["expected_pages"]:
            for path in group.split("|"):
                assert re.fullmatch(r"[a-z0-9-]+(/[a-z0-9-]+)*", path), path


def test_page_recall_counts_alternatives_and_ignores_anchors():
    cited = [
        "https://docs.rhesis.ai/sdk/metrics#metric-scopes",
        "https://docs.rhesis.ai/sdk/installation",
    ]
    assert page_recall(["docs/metrics/metric-scope|sdk/metrics"], cited) == 1.0
    assert page_recall(["sdk/installation", "guides/ci-cd-integration"], cited) == 0.5
    assert page_recall([], cited) is None


def test_route_ok_accepts_listed_alternatives():
    row = {"expected_route": "not_documented", "also_ok": ["false_premise"]}
    assert route_ok(row, "false_premise")
    assert not route_ok(row, "answered")


def test_summary_skips_rows_without_pages_for_recall():
    results = [
        RowResult("a", "answered", "answered", True, 1.0, [], [], 1.0),
        RowResult("b", "smalltalk", "answered", False, None, [], [], 3.0),
    ]
    summary = summarize(results)
    assert summary["route_correct"] == 1
    assert summary["page_recall"] == 1.0
    assert summary["mean_seconds"] == 2.0

"""Test sets, the tests in them, and their metrics."""

from __future__ import annotations

from project_migrate.api import PAGE, Abort
from project_migrate.compare import clean
from project_migrate.engine import Migration, index_by_name


def test_sets(m: Migration) -> None:
    allowed = m.props("TestSetCreate")
    existing = index_by_name(m.dst.get_all("/test_sets/", **m.dst.project_filter()))
    for ts in m.snap["test_sets"]:
        # attributes and slug are computed by the server.
        payload = clean(
            ts, allowed, frozenset({"attributes", "slug", "test_set_type_id", "priority"})
        )
        set_type = ts.get("test_set_type") or {}
        payload["test_set_type_id"] = m.type_lookup(
            set_type.get("type_name", "TestSetType"), set_type.get("type_value", "Single-Turn")
        )
        sid = m.upsert_named("test set", ts, payload, existing, "/test_sets/")
        _link_tests(m, ts, sid)
        _link_metrics(m, ts, sid)


def _set_test_ids(m: Migration, sid: str) -> set[str]:
    return {t["id"] for t in m.dst.get_all(f"/test_sets/{sid}/tests")}


def _link_tests(m: Migration, ts: dict, sid: str) -> None:
    have = set() if m.is_placeholder(sid) else _set_test_ids(m, sid)
    want = [m.mapped("test", x) for x in ts["_test_ids"]]
    unmapped = [x for x, w in zip(ts["_test_ids"], want, strict=True) if not w]
    if unmapped and m.limit is None:
        raise Abort(f"test set '{ts['name']}' has tests missing from the snapshot: {unmapped[:5]}")
    wanted = [w for w in want if w]
    m.report.add("test set-test link", "linked", sum(1 for w in wanted if w in have))
    todo = [w for w in wanted if w not in have]
    if todo:
        m.report.add("test set-test link", "link", len(todo))
    for i in range(0, len(todo), PAGE):
        chunk = todo[i : i + PAGE]

        def exists(chunk: list[str] = chunk) -> bool:
            return set(chunk) <= _set_test_ids(m, sid)

        m.post_link(f"/test_sets/{sid}/associate", exists, body={"test_ids": chunk})
    extra = len(have - set(wanted))
    if extra:
        m.report.notes.append(
            f"test set '{ts['name']}' has {extra} extra test(s) on the target (left alone)"
        )


def _link_metrics(m: Migration, ts: dict, sid: str) -> None:
    def current() -> set[str]:
        return {x["id"] for x in m.dst.get(f"/test_sets/{sid}/metrics")}

    have = set() if m.is_placeholder(sid) else current()
    for src_metric in ts["_metrics"]:
        mid = m.metric_target(src_metric)
        if mid in have:
            m.report.add("test set-metric link", "linked")
            continue
        m.report.add("test set-metric link", "link")

        def exists(mid: str = mid) -> bool:
            return mid in current()

        m.post_link(f"/test_sets/{sid}/metrics/{mid}", exists)

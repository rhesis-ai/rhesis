"""Read a source project into one JSON document. The only step that touches the source."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone

from project_migrate.api import Api, HttpError

FORMAT_VERSION = 1


def take_snapshot(src: Api, log: Callable[[str], None] = print) -> dict:
    pf = src.project_filter()
    project = src.get(f"/projects/{src.project_id}")
    log(f"Snapshot of '{project['name']}' from {src.base}")

    endpoints = [src.get(f"/endpoints/{e['id']}") for e in src.get_all("/endpoints/", **pf)]
    requirements = src.get_all("/requirements/", **pf)
    metrics = [src.get(f"/metrics/{m['id']}") for m in src.get_all("/metrics/", **pf)]
    tests = src.get_all("/tests/", **pf)
    # The prompt nested in a test has no language_code, so prompts are listed on their own.
    prompts = {p["id"]: p for p in src.get_all("/prompts/", **pf)}
    test_sets = src.get_all("/test_sets/", **pf)
    known_tests = {t["id"] for t in tests}
    for ts in test_sets:
        members = src.get_all(f"/test_sets/{ts['id']}/tests")
        ts["_test_ids"] = [t["id"] for t in members]
        ts["_metrics"] = src.get(f"/test_sets/{ts['id']}/metrics")
        # A set can hold tests with no project; they aren't in the project list but must move.
        for t in members:
            if t["id"] not in known_tests:
                tests.append(t)
                known_tests.add(t["id"])

    _add_referenced_requirements(src, tests, requirements, log)
    metrics += _referenced_project_metrics(src, requirements, test_sets, metrics)
    org_metrics = _referenced_org_metrics(src, requirements, test_sets)
    for t in tests:
        pid = t.get("prompt_id")
        t["_prompt"] = prompts.get(pid) or (src.get(f"/prompts/{pid}") if pid else None)

    return {
        "format_version": FORMAT_VERSION,
        "meta": {
            "taken_at": datetime.now(timezone.utc).isoformat(),
            "src_url": src.base,
            "src_project_id": src.project_id,
            "src_api_version": src.get("/openapi.json")["info"].get("version"),
        },
        "project": project,
        "endpoints": endpoints,
        "requirements": requirements,
        "metrics": metrics,
        "org_metrics": org_metrics,
        "tests": tests,
        "test_sets": test_sets,
    }


def _add_referenced_requirements(
    src: Api, tests: list[dict], requirements: list[dict], log: Callable[[str], None]
) -> None:
    """Tests can point at requirements outside the project list; they must exist on the target."""
    known = {r["id"]: r for r in requirements}
    for t in tests:
        rid = t.get("requirement_id")
        if rid in known and not t.get("requirement"):
            # Keep the embedded copy consistent; the test fingerprint reads its name.
            t["requirement"] = {"id": rid, "name": known[rid]["name"]}
        if not rid or rid in known:
            continue
        try:
            fetched = src.get(f"/requirements/{rid}")
            requirements.append(fetched)
            known[rid] = fetched
        except HttpError as e:
            if e.status != 410:
                raise
            # Soft-deleted on the source but still used: rebuild it from the copy in the test,
            # or from the name the 410 response carries when the test no longer embeds it.
            nested = t.get("requirement") or {
                "id": rid,
                "name": (e.body or {}).get("item_name") or f"Deleted requirement {rid}",
            }
            nested = {**nested, "_deleted_on_source": True}
            requirements.append(nested)
            known[rid] = nested
            t["requirement"] = {"id": rid, "name": nested["name"]}
            log(
                f"  note: requirement '{nested['name']}' is deleted on the source but still "
                "used by tests; it will be created on the target"
            )


def _linked_metrics(requirements: list[dict], test_sets: list[dict]) -> list[dict]:
    linked = [m for r in requirements for m in (r.get("metrics") or [])]
    return linked + [m for ts in test_sets for m in ts["_metrics"]]


def _referenced_project_metrics(
    src: Api, requirements: list[dict], test_sets: list[dict], metrics: list[dict]
) -> list[dict]:
    """Custom metrics from another project that are linked here."""
    known = {m["id"] for m in metrics}
    out: list[dict] = []
    for m in _linked_metrics(requirements, test_sets):
        if m["id"] not in known and m.get("project_id"):
            out.append(src.get(f"/metrics/{m['id']}"))
            known.add(m["id"])
    return out


def _referenced_org_metrics(
    src: Api, requirements: list[dict], test_sets: list[dict]
) -> list[dict]:
    """Linked metrics with no project: built-ins, or custom metrics made at org level. Kept in
    full, so the target can match a built-in or get a copy of a custom one."""
    out: dict[str, dict] = {}
    for m in _linked_metrics(requirements, test_sets):
        if not m.get("project_id") and m["id"] not in out:
            out[m["id"]] = src.get(f"/metrics/{m['id']}")
    return list(out.values())


def summary(snap: dict) -> str:
    in_sets = {tid for ts in snap["test_sets"] for tid in ts["_test_ids"]}
    return (
        f"endpoints={len(snap['endpoints'])} requirements={len(snap['requirements'])} "
        f"custom_metrics={len(snap['metrics'])} tests={len(snap['tests'])} "
        f"(in sets: {len(in_sets)}) test_sets={len(snap['test_sets'])}"
    )

"""Preflight, endpoints, requirements, metrics, their links, topics and categories."""

from __future__ import annotations

from project_migrate.api import PAGE, Abort
from project_migrate.compare import clean, lookup_value
from project_migrate.engine import Migration, index_by_name

# The API never returns these, so they can't be copied. They're re-entered by hand.
ENDPOINT_SECRET_FIELDS = frozenset(
    {"auth_token", "client_secret", "last_token", "has_auth_token", "has_client_secret"}
)


def preflight(m: Migration) -> None:
    proj = m.dst.get(f"/projects/{m.dst.project_id}")
    m.log(f"Target project: '{proj['name']}' on {m.dst.base}")
    for kind, key in (
        ("endpoints", "name"),
        ("requirements", "name"),
        ("metrics", "name"),
        ("test_sets", "name"),
        ("sources", "title"),
        ("experiments", "name"),
    ):
        names = [x[key] for x in m.snap.get(kind) or []]
        dupes = sorted({n for n in names if names.count(n) > 1})
        if dupes:
            raise Abort(f"source has duplicate {kind} names {dupes}; names are the match key")
    models = m.dst.get("/models/", limit=PAGE)
    m.log(
        f"  target models: {[x['name'] for x in models]} "
        "(copied metrics have no model set and use the org default judge model)"
    )


# Header names that usually carry a credential.
CREDENTIAL_HINTS = ("authorization", "api-key", "api_key", "apikey", "token", "secret", "password")


def is_sdk_endpoint(e: dict) -> bool:
    """SDK endpoints are registered by a running connector, not configured by URL, so the
    connector has to register them against the target itself."""
    return e.get("connection_type") == "SDK"


def literal_credential_headers(e: dict) -> list[str]:
    """Headers that look like credentials and hold a value rather than a template."""
    return sorted(
        name
        for name, value in (e.get("request_headers") or {}).items()
        if any(hint in name.lower() for hint in CREDENTIAL_HINTS)
        and isinstance(value, str)
        and "{{" not in value
    )


def endpoints(m: Migration) -> None:
    allowed = m.props("EndpointCreate")
    existing = index_by_name(m.dst.get_all("/endpoints/", **m.dst.project_filter()))
    for e in m.snap["endpoints"]:
        if is_sdk_endpoint(e):
            m.report.add("endpoint", "skipped")
            m.report.notes.append(
                f"endpoint '{e['name']}' is an SDK endpoint; point its connector at the target "
                "so it registers there"
            )
            continue
        payload = clean(e, allowed, ENDPOINT_SECRET_FIELDS | {"is_example"})
        m.upsert_named("endpoint", e, payload, existing, "/endpoints/", refetch="")
        if e.get("has_auth_token") or e.get("has_client_secret"):
            m.report.notes.append(
                f"endpoint '{e['name']}' has a secret on the source; set it in the target UI"
            )
        literal = literal_credential_headers(e)
        if literal:
            m.report.notes.append(
                f"endpoint '{e['name']}' sends credential header(s) {literal} as plain values; "
                "they were copied as they are, so check they are right for the target"
            )


def requirements(m: Migration) -> None:
    allowed = m.props("RequirementCreate")
    m.dst_requirements = m.dst.get_all("/requirements/", **m.dst.project_filter())
    existing = index_by_name(m.dst_requirements)
    pending = list(m.snap["requirements"])
    pending_ids = {r["id"] for r in pending}
    while pending:
        ready = [r for r in pending if r.get("parent_id") not in pending_ids]
        if not ready:
            raise Abort("requirement parent cycle in the source")
        for r in ready:
            payload = clean(r, allowed, frozenset({"parent_id", "impact_id"}))
            if r.get("parent_id"):
                payload["parent_id"] = m.mapped("requirement", r["parent_id"])
            if r.get("impact"):
                impact = r["impact"]
                payload["impact_id"] = m.type_lookup(impact["type_name"], impact["type_value"])
            payload = {k: v for k, v in payload.items() if v is not None}
            m.upsert_named("requirement", r, payload, existing, "/requirements/")
            pending.remove(r)
            pending_ids.discard(r["id"])


def _metric_normalize(t: dict) -> dict:
    return {
        **t,
        "metric_type": lookup_value(t.get("metric_type")),
        "backend_type": lookup_value(t.get("backend_type")),
    }


def metrics(m: Migration) -> None:
    allowed = m.props("MetricCreate")
    m.dst_metrics = m.dst.get_all("/metrics/")
    mine = index_by_name([x for x in m.dst_metrics if x.get("project_id") == m.dst.project_id])
    for src in m.snap["metrics"]:
        _upsert_metric(m, src, allowed, mine)
    for src in m.snap.get("org_metrics", []):
        hits = m.builtin_matches(src)
        if len(hits) == 1:
            m.remember("metric", src["id"], hits[0]["id"])
        elif hits:
            raise Abort(f"target has {len(hits)} org-level metrics named '{src['name']}'")
        else:
            # A custom metric made at org level on the source: copy it into the project.
            m.report.notes.append(f"org-level metric '{src['name']}' copied into the project")
            _upsert_metric(m, src, allowed, mine)


def _upsert_metric(m: Migration, src: dict, allowed: set[str], mine: dict) -> None:
    drop = frozenset(
        {"metric_type_id", "backend_type_id", "model_id", "metric_type", "backend_type"}
    )
    payload = clean(src, allowed, drop)
    # Sent as names; the backend creates the lookup if the target lacks it.
    for k in ("metric_type", "backend_type"):
        if lookup_value(src.get(k)):
            payload[k] = lookup_value(src[k])
    m.upsert_named(
        "metric", src, payload, mine, "/metrics/", normalize=_metric_normalize, refetch=""
    )


def requirement_metric_links(m: Migration) -> None:
    dst_reqs = {r["id"]: r for r in m.dst_requirements}
    for r in m.snap["requirements"]:
        rid = m.mapped("requirement", r["id"])
        have = {x["id"] for x in (dst_reqs.get(rid, {}).get("metrics") or [])}
        for src_metric in r.get("metrics") or []:
            mid = m.metric_target(src_metric)
            if mid in have:
                m.report.add("requirement-metric link", "linked")
                continue
            m.report.add("requirement-metric link", "link")

            def exists(rid: str = rid, mid: str = mid) -> bool:
                return mid in {x["id"] for x in m.dst.get(f"/requirements/{rid}/metrics/")}

            m.post_link(f"/requirements/{rid}/metrics/{mid}", exists)
        if m.prune:
            wanted = {m.metric_target(x) for x in r.get("metrics") or []}
            for extra in sorted(have - wanted):
                m.unlink(
                    "requirement-metric link",
                    "DELETE",
                    f"/requirements/{rid}/metrics/{extra}",
                    label=f"requirement '{r['name']}' -> metric {extra}",
                )


def topics_and_categories(m: Migration) -> None:
    for kind, path in (("topic", "/topics/"), ("category", "/categories/")):
        # Prefer one in the target project, else an org-wide one (no project).
        idx: dict[str, list[dict]] = {}
        for row in m.dst.get_all(path):
            if row.get("project_id") in (m.dst.project_id, None):
                idx.setdefault(row["name"], []).append(row)
        for name, rows in idx.items():
            idx[name] = sorted(rows, key=lambda r: r.get("project_id") is None)[:1]
        seen: set[str] = set()
        for t in m.snap["tests"]:
            src = t.get(kind)
            if not src or src["id"] in seen:
                continue
            seen.add(src["id"])
            # Name only: an org-wide topic may be shared, so its description is never rewritten.
            m.upsert_named(kind, src, {"name": src["name"]}, idx, path)

"""Project-level data: the parameter schema, sources, and the sources linked to requirements."""

from __future__ import annotations

from project_migrate.api import HttpError
from project_migrate.compare import changed_fields, clean, lookup_value
from project_migrate.engine import Migration, index_by_name

KIND_SCHEMA = "parameter schema"
KIND_LINK = "requirement-source link"
# Where the source instance stored the uploaded file. The file itself isn't copied, so these
# would point at nothing on the target.
SOURCE_STORAGE_KEYS = frozenset({"file_path", "file_hash"})


def _schema_fields(m: Migration, fields: list[dict]) -> list[dict]:
    """Keep only the field keys the target's ParameterField accepts, so a newer source's extra
    keys don't show as a change on every run."""
    try:
        allowed = m.props("ParameterField")
    except KeyError:
        return fields
    return [{k: v for k, v in f.items() if k in allowed} for f in fields]


def parameter_schema(m: Migration) -> None:
    """Fields are matched by name. A field only the target has is kept unless --prune is set,
    and a source with no fields leaves the target alone."""
    want = m.snap.get("parameter_schema")
    if not want or not want.get("fields"):
        return  # an older snapshot, a source without the parameters API, or nothing to copy
    path = f"/projects/{m.dst.project_id}/parameters/schema"
    try:
        have = m.dst.get(path)
    except HttpError as e:
        if e.status != 404:
            raise
        m.report.notes.append("the target has no parameters API; the parameter schema was skipped")
        return
    src_fields = _schema_fields(m, want["fields"])
    src_names = {f["name"] for f in src_fields}
    extra = [f for f in have.get("fields", []) if f["name"] not in src_names]
    merged = src_fields if m.prune else src_fields + extra
    if not changed_fields({"fields": merged}, have):
        m.report.add(KIND_SCHEMA, "unchanged")
        return
    m.report.add(KIND_SCHEMA, "update")
    dropped = [f["name"] for f in extra] if m.prune else []
    m.log(f"  update parameter schema{f' (removing {dropped})' if dropped else ''}")
    m.put(path, {"fields": merged})


def sources(m: Migration) -> None:
    if not m.snap.get("sources"):
        return
    try:
        allowed = m.props("SourceCreate")
        rows = m.dst.get_all("/sources/", **m.dst.project_filter())
    except (KeyError, HttpError) as e:
        if isinstance(e, HttpError) and e.status != 404:
            raise
        m.sources_skipped = True
        m.report.notes.append("the target has no sources API; sources and their links were skipped")
        return
    existing = index_by_name(rows, key="title")
    for src in m.snap["sources"]:
        payload = clean(src, allowed, frozenset({"source_type_id"}))
        if payload.get("source_metadata"):
            payload["source_metadata"] = {
                k: v for k, v in payload["source_metadata"].items() if k not in SOURCE_STORAGE_KEYS
            }
        source_type = src.get("source_type")
        if lookup_value(source_type):
            payload["source_type_id"] = m.type_lookup(
                source_type.get("type_name") or "SourceType", lookup_value(source_type)
            )
        # The list route leaves out the text content, so compare against the content route.
        m.upsert_named(
            "source", src, payload, existing, "/sources/", key="title", refetch="/content"
        )


def requirement_source_links(m: Migration) -> None:
    if "sources" not in m.snap or m.sources_skipped:
        # A snapshot from before sources were copied, or a target that can't hold them: none
        # of these links can be mapped.
        return
    dst_reqs = {r["id"]: r for r in m.dst_requirements}
    for r in m.snap["requirements"]:
        rid = m.mapped("requirement", r["id"])
        have = {x["id"]: x.get("note") for x in (dst_reqs.get(rid, {}).get("sources") or [])}
        wanted, complete = _link_sources(m, r, rid, have)
        # Never prune against an incomplete list: an unmapped link would look like an extra.
        if m.prune and complete and rid and not m.is_placeholder(rid):
            for extra in sorted(set(have) - wanted):
                m.unlink(
                    KIND_LINK,
                    "DELETE",
                    f"/requirements/{rid}/sources/{extra}",
                    label=f"requirement '{r['name']}' -> source {extra}",
                )


def _link_sources(
    m: Migration, r: dict, rid: str | None, have: dict[str, str | None]
) -> tuple[set[str], bool]:
    wanted: set[str] = set()
    complete = True
    for link in r.get("sources") or []:
        sid = m.mapped("source", link["id"])
        if not sid:
            complete = False
            m.report.notes.append(
                f"requirement '{r['name']}' links a source missing from the snapshot"
            )
            continue
        wanted.add(sid)
        if sid in have and have[sid] == link.get("note"):
            m.report.add(KIND_LINK, "linked")
            continue
        # The same POST creates the link or updates its note.
        m.report.add(KIND_LINK, "link")

        def exists(sid: str = sid, note: str | None = link.get("note")) -> bool:
            linked = m.dst.get(f"/requirements/{rid}").get("sources") or []
            return any(x["id"] == sid and x.get("note") == note for x in linked)

        m.post_link(f"/requirements/{rid}/sources/{sid}", exists, body={"note": link.get("note")})
    return wanted, complete

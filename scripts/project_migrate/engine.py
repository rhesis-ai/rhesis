"""The sync engine shared by plan, apply and verify.

plan and verify run it with dry=True: nothing is written and creates get placeholder ids, so
the later steps still see what they would link.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from project_migrate.api import Abort, AmbiguousWrite, Api, HttpError, odata_str
from project_migrate.compare import changed_fields
from project_migrate.state import State

ACTIONS = (
    "unchanged",
    "linked",
    "create",
    "update",
    "link",
    "unlink",
    "adopt",
    "skipped",
    "kept",
    "diverged",
    "refused",
)
UNCLEAR_RETRIES = 3
UNCLEAR_WAIT_SECONDS = 5.0


@dataclass
class Report:
    rows: dict[str, dict[str, int]] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def add(self, kind: str, action: str, n: int = 1) -> None:
        row = self.rows.setdefault(kind, {})
        row[action] = row.get(action, 0) + n

    def pending_work(self) -> int:
        return sum(
            n
            for r in self.rows.values()
            for a, n in r.items()
            if a not in ("unchanged", "linked", "skipped", "kept")
        )

    def render(self) -> str:
        # Only the columns some row uses, so the table stays readable.
        used = [a for a in ACTIONS if any(a in r for r in self.rows.values())]
        lines = [f"{'entity':<26}" + "".join(f"{a:>11}" for a in used)]
        for kind, r in self.rows.items():
            lines.append(f"{kind:<26}" + "".join(f"{r.get(a, 0):>11}" for a in used))
        lines += [f"  note: {n}" for n in self.notes]
        return "\n".join(lines)


class Migration:
    def __init__(
        self,
        snap: dict,
        dst: Api,
        state: State,
        *,
        dry: bool,
        limit: int | None = None,
        prune: bool = False,
        log: Callable[[str], None] = print,
    ):
        self.snap = snap
        self.dst = dst
        self.state = state
        self.dry = dry
        self.limit = limit
        self.prune = prune
        self.log = log
        self.report = Report()
        self.placeholders = 0
        self.ids: dict[str, dict[str, str]] = {}  # kind -> source id -> target id
        self.lookups: dict[str, str] = {}
        self.schemas: dict = {}
        # Filled by the steps for the ones that come after them.
        self.dst_requirements: list[dict] = []
        self.dst_metrics: list[dict] = []
        self.sources_skipped = False
        self.experiments_skipped = False

    # ---- ids --------------------------------------------------------------------------------

    def remember(self, kind: str, src_id: str, dst_id: str) -> None:
        self.ids.setdefault(kind, {})[src_id] = dst_id

    def mapped(self, kind: str, src_id: str | None) -> str | None:
        return self.ids.get(kind, {}).get(src_id) if src_id else None

    def is_placeholder(self, target_id: str) -> bool:
        return target_id.startswith("DRY-")

    # ---- target schema ----------------------------------------------------------------------

    def props(self, schema: str) -> set[str]:
        """Fields the target's create schema accepts. The target may run an older version."""
        if not self.schemas:
            self.schemas = self.dst.get("/openapi.json")["components"]["schemas"]
        return set(self.schemas[schema]["properties"])

    def type_lookup(self, type_name: str, type_value: str) -> str:
        key = f"{type_name}/{type_value}"
        if key not in self.lookups:
            rows = self.dst.get(
                "/type_lookups/",
                **{
                    "$filter": f"type_name eq {odata_str(type_name)} and "
                    f"type_value eq {odata_str(type_value)}"
                },
            )
            if not rows:
                raise Abort(f"target has no type lookup {key}")
            self.lookups[key] = rows[0]["id"]
        return self.lookups[key]

    # ---- writes -----------------------------------------------------------------------------

    def create(
        self, kind: str, path: str, payload: dict, reconcile: Callable[[], dict | None]
    ) -> str:
        """POST once. If the outcome is unclear, look for the record before posting again."""
        if self.dry:
            self.placeholders += 1
            return f"DRY-{self.placeholders}"
        for _ in range(UNCLEAR_RETRIES):
            try:
                return self.dst.request("POST", path, body=payload)["id"]
            except AmbiguousWrite as e:
                self.log(f"  unclear create for {kind} ({e}); checking target")
                self.dst.clock.sleep(UNCLEAR_WAIT_SECONDS)
                found = reconcile()
                if found:
                    self.report.add(kind, "adopt")
                    return found["id"]
        raise Abort(f"could not create {kind} after {UNCLEAR_RETRIES} unclear attempts")

    def put(self, path: str, body: dict) -> None:
        self.send("PUT", path, body)

    def send(self, method: str, path: str, body: dict | None = None) -> None:
        """An idempotent write (PUT, PATCH, DELETE), skipped in a dry run."""
        if not self.dry:
            self.dst.request(method, path, body=body)

    def post_link(self, path: str, exists: Callable[[], bool], body: dict | None = None) -> None:
        """Add a link. After an unclear outcome, re-read the links instead of posting blind."""
        if self.dry:
            return
        for _ in range(UNCLEAR_RETRIES):
            try:
                self.dst.request("POST", path, body=body)
                return
            except AmbiguousWrite:
                self.dst.clock.sleep(UNCLEAR_WAIT_SECONDS)
                if exists():
                    return
        raise Abort(f"could not create link {path}")

    def upsert_named(
        self,
        kind: str,
        src: dict,
        payload: dict,
        index: dict[str, list[dict]],
        path: str,
        *,
        key: str = "name",
        normalize: Callable[[dict], dict] = lambda x: x,
        refetch: str | None = None,
    ) -> str:
        """Create or update an entity matched by `key` (its name) in the target project.

        `refetch` is a path suffix: when set, the target record is read again from
        `<path><id><refetch>` before comparing, for fields the list route leaves out.
        """
        label = src[key]
        target = self._find_named(kind, src, index, key)
        if target:
            if refetch is not None:
                target = self.dst.get(f"{path}{target['id']}{refetch}")
            diff = changed_fields(payload, normalize(target))
            if diff:
                self.report.add(kind, "update")
                self.log(f"  update {kind} '{label}': {diff}")
                self.put(f"{path}{target['id']}", {k: payload[k] for k in diff})
            else:
                self.report.add(kind, "unchanged")
            self._done(kind, src, target["id"], label)
            return target["id"]

        self.report.add(kind, "create")
        self.log(f"  create {kind} '{label}'")
        self.state.put(f"{kind}:{src['id']}", status="pending", name=label)

        def reconcile() -> dict | None:
            found = self.dst.get(
                path,
                **{
                    "$filter": f"{key} eq {odata_str(label)} and "
                    f"project_id eq {odata_str(self.dst.project_id)}"
                },
            )
            return found[0] if found else None

        body = {**payload, "project_id": self.dst.project_id}
        new_id = self.create(kind, path, body, reconcile)
        index.setdefault(label, []).append({"id": new_id, key: label})
        self._done(kind, src, new_id, label)
        return new_id

    def _find_named(
        self, kind: str, src: dict, index: dict[str, list[dict]], key: str
    ) -> dict | None:
        entry = self.state.get(f"{kind}:{src['id']}") or {}
        if entry.get("target_id"):
            for rows in index.values():
                for row in rows:
                    if row["id"] == entry["target_id"]:
                        return row
            self.report.notes.append(
                f"{kind} '{src[key]}' was in state but is gone on the target; recreating"
            )
        matches = index.get(src[key], [])
        if len(matches) > 1:
            raise Abort(f"target has {len(matches)} {kind}s named '{src[key]}'; resolve by hand")
        return matches[0] if matches else None

    def _done(self, kind: str, src: dict, target_id: str, label: str) -> None:
        self.state.put(f"{kind}:{src['id']}", status="done", target_id=target_id, name=label)
        self.remember(kind, src["id"], target_id)

    def unlink(
        self,
        kind: str,
        method: str,
        path: str,
        *,
        label: str,
        body: dict | None = None,
        count: int = 1,
        gone: Callable[[], bool] | None = None,
    ) -> None:
        """Remove target links the source doesn't have. Only called with --prune.

        A 404 means the link is already gone (a retried DELETE whose first try went through).
        An unclear POST is checked with `gone` before it is sent again.
        """
        self.report.add(kind, "unlink", count)
        self.log(f"  unlink {kind}: {label}")
        if self.dry:
            return
        for _ in range(UNCLEAR_RETRIES):
            try:
                self.dst.request(method, path, body=body)
                return
            except HttpError as e:
                if e.status == 404:
                    return
                raise
            except AmbiguousWrite:
                self.dst.clock.sleep(UNCLEAR_WAIT_SECONDS)
                if gone and gone():
                    return
        raise Abort(f"could not remove link {path}")

    # ---- metrics shared by several steps ----------------------------------------------------

    def metric_target(self, src_metric: dict) -> str:
        mapped = self.mapped("metric", src_metric["id"])
        if mapped:
            return mapped
        # A built-in: each instance seeds its own, so match the target's copy.
        hits = self.builtin_matches(src_metric)
        if len(hits) != 1:
            raise Abort(
                f"cannot match built-in metric '{src_metric['name']}' on the target "
                f"({len(hits)} candidates)"
            )
        self.remember("metric", src_metric["id"], hits[0]["id"])
        return hits[0]["id"]

    def builtin_matches(self, src_metric: dict) -> list[dict]:
        return [
            m
            for m in self.dst_metrics
            if not m.get("project_id")
            and m["name"] == src_metric["name"]
            and m.get("class_name") == src_metric.get("class_name")
        ]


def index_by_name(rows: list[dict], key: str = "name") -> dict[str, list[dict]]:
    idx: dict[str, list[dict]] = {}
    for r in rows:
        idx.setdefault(r[key], []).append(r)
    return idx

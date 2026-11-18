"""An in-memory Rhesis instance that speaks just the routes the migration tool calls.

It plugs into `Api(transport=...)`, so no network, Docker or backend is involved. Faults can be
queued to make a request fail in a specific way (see `fail` and `crash_after_writes`).
"""

from __future__ import annotations

import copy
import itertools
import json
import re
import uuid
from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse

from project_migrate.api import ConnectFailed, Response, SendFailed

TABLES = (
    "projects",
    "endpoints",
    "requirements",
    "metrics",
    "topics",
    "categories",
    "prompts",
    "tests",
    "test_sets",
    "type_lookups",
    "models",
    "sources",
)

SCHEMAS = {
    "EndpointCreate": [
        "project_id", "name", "description", "connection_type", "url", "auth", "environment",
        "method", "endpoint_path", "request_headers", "query_params", "request_mapping",
        "response_mapping", "endpoint_metadata", "auth_type", "auth_token", "is_example",
    ],
    "RequirementCreate": ["project_id", "name", "description", "parent_id", "impact_id"],
    "MetricCreate": [
        "project_id", "name", "description", "evaluation_prompt", "evaluation_steps",
        "score_type", "categories", "passing_categories", "threshold", "threshold_operator",
        "metric_type", "backend_type", "metric_type_id", "backend_type_id", "class_name",
        "metric_scope", "model_id", "config",
    ],
    "SourceCreate": [
        "project_id", "title", "description", "source_type_id", "source_metadata", "content",
    ],
    "ParameterField": [
        "name", "type", "description", "required", "default", "options", "display_order",
    ],
    "TestSetCreate": [
        "project_id", "name", "description", "short_description", "slug", "test_set_type_id",
        "attributes", "priority",
    ],
}  # fmt: skip


class Crash(BaseException):
    """Stands in for the process dying: nothing in the tool catches a BaseException."""


@dataclass
class Fault:
    method: str
    path: re.Pattern
    mode: str  # see FakeRhesis.fail
    retry_after: str | None = None


class FakeRhesis:
    def __init__(self, clock=None):
        self.db: dict[str, dict[str, dict]] = {t: {} for t in TABLES}
        self.req_metric: set[tuple[str, str]] = set()
        self.req_source: dict[tuple[str, str], str | None] = {}  # (requirement, source) -> note
        self.has_parameters_api = True
        self.has_sources_api = True
        self.has_experiments_api = True
        self.experiments: dict[str, dict] = {}
        self.environments: dict[str, dict[str, dict | None]] = {}  # project -> name -> pointer
        self.set_tests: dict[str, list[str]] = {}
        self.set_metrics: dict[str, list[str]] = {}
        self.deleted: set[str] = set()
        self.faults: list[Fault] = []
        self.crash_at: int | None = None
        self.crash_before_commit = False
        self.writes = 0
        self.write_times: list[float] = []
        self.log: list[tuple[str, str, dict | None]] = []
        self.clock = clock
        self._seq = itertools.count()
        for type_name, value in (
            ("TestType", "Single-Turn"),
            ("TestType", "Multi-Turn"),
            ("TestSetType", "Single-Turn"),
            ("RequirementImpact", "High"),
            ("SourceType", "Document"),
        ):
            self.insert("type_lookups", type_name=type_name, type_value=value)
        self.insert("models", name="Default judge")

    # ---- seeding ----------------------------------------------------------------------------

    def insert(self, table: str, **row) -> dict:
        row.setdefault("id", str(uuid.uuid4()))
        row["_seq"] = next(self._seq)
        self.db[table][row["id"]] = row
        return row

    def lookup_id(self, type_name: str, value: str) -> str:
        for r in self.db["type_lookups"].values():
            if r["type_name"] == type_name and r["type_value"] == value:
                return r["id"]
        return self.insert("type_lookups", type_name=type_name, type_value=value)["id"]

    # ---- faults -----------------------------------------------------------------------------

    def fail(self, method: str, path: str, mode: str, retry_after: str | None = None) -> None:
        """Queue one fault for the next matching request.

        mode: "commit_then_drop" (server saves, client sees a broken connection),
        "commit_then_500" (server saves, then answers 500),
        "drop" (broken connection, nothing saved), "connect" (never reached the server),
        or an HTTP status such as "429", "503", "422".
        """
        self.faults.append(Fault(method, re.compile(path), mode, retry_after))

    def crash_after_writes(self, n: int, before_commit: bool = False) -> None:
        """Kill the client on write number n, after (default) or before the server saves it."""
        self.crash_at = self.writes + n
        self.crash_before_commit = before_commit

    # ---- transport --------------------------------------------------------------------------

    def __call__(self, method, url, headers, body, timeout) -> Response:
        parsed = urlparse(url)
        path = parsed.path
        query = {k: v[0] for k, v in parse_qs(parsed.query).items()}
        payload = json.loads(body) if body else None
        fault = self._take_fault(method, path)
        if fault and fault.mode == "connect":
            raise ConnectFailed("fake: connection refused")
        if fault and fault.mode == "drop":
            raise SendFailed("fake: connection reset")
        if fault and fault.mode.isdigit():
            # Lowercase, as uvicorn sends it.
            headers = {"retry-after": fault.retry_after} if fault.retry_after else {}
            return Response(int(fault.mode), headers, b'{"detail": "fake fault"}')

        if method != "GET":
            self.writes += 1
            if self.clock:
                self.write_times.append(self.clock.monotonic())
            if self.crash_at == self.writes and self.crash_before_commit:
                raise Crash()
        self.log.append((method, path, payload))
        status, data = self._route(method, path, query, payload)
        if method != "GET" and self.crash_at == self.writes and not self.crash_before_commit:
            raise Crash()
        if fault and fault.mode == "commit_then_drop":
            raise SendFailed("fake: read timed out after commit")
        if fault and fault.mode == "commit_then_500":
            return Response(500, {}, b'{"detail": "fake error after commit"}')
        return Response(status, {}, json.dumps(data).encode())

    def _take_fault(self, method: str, path: str) -> Fault | None:
        for f in self.faults:
            if f.method == method and f.path.search(path):
                self.faults.remove(f)
                return f
        return None

    # ---- routing ----------------------------------------------------------------------------

    def _route(self, method: str, path: str, q: dict, body: dict | None) -> tuple[int, object]:
        if path.startswith("/sources") and not self.has_sources_api:
            return 404, {"detail": "Not Found"}
        if path == "/openapi.json":
            schemas = {n: {"properties": {p: {} for p in ps}} for n, ps in SCHEMAS.items()}
            if not self.has_sources_api:
                schemas.pop("SourceCreate")
            return 200, {"info": {"version": "0.0.0-fake"}, "components": {"schemas": schemas}}
        if int(q.get("limit", "0")) > 100:
            return 400, {"detail": "limit too large"}

        if not self.has_experiments_api and (
            "/experiments" in path or "/parameters/environments" in path
        ):
            return 404, {"detail": "Not Found"}
        links = [
            (r"^/projects/([^/]+)/parameters/schema$", self._parameter_schema),
            (r"^/projects/([^/]+)/experiments$", self._project_experiments),
            (r"^/experiments/([^/]+)$", self._experiment),
            (r"^/experiments/([^/]+)/versions$", self._experiment_versions),
            (r"^/projects/([^/]+)/parameters/environments$", self._environments),
            (r"^/projects/([^/]+)/parameters/environments/([^/]+)$", self._environment),
            (r"^/sources/([^/]+)/content$", self._source_content),
            (r"^/requirements/([^/]+)/sources/([^/]+)$", self._req_source_link),
            (r"^/test_sets/([^/]+)/disassociate$", self._disassociate),
            (r"^/requirements/([^/]+)/metrics/$", self._req_metrics),
            (r"^/requirements/([^/]+)/metrics/([^/]+)$", self._req_metric_link),
            (r"^/test_sets/([^/]+)/tests$", self._set_tests_list),
            (r"^/test_sets/([^/]+)/associate$", self._associate),
            (r"^/test_sets/([^/]+)/metrics$", self._set_metrics_list),
            (r"^/test_sets/([^/]+)/metrics/([^/]+)$", self._set_metric_link),
        ]
        for pattern, handler in links:
            match = re.match(pattern, path)
            if match:
                return handler(method, q, body, *match.groups())

        match = re.match(r"^/([a-z_]+)/([^/]*)$", path)
        if not match or match.group(1) not in TABLES:
            return 404, {"detail": f"no route {path}"}
        table, item_id = match.groups()
        if item_id:
            return self._item(method, table, item_id, body)
        if method == "GET":
            return 200, self._list(table, q)
        if method == "POST":
            return self._create(table, body)
        return 405, {"detail": "method not allowed"}

    def _list(self, table: str, q: dict) -> list[dict]:
        rows = sorted(self.db[table].values(), key=lambda r: r["_seq"])
        if q.get("sort_order") == "desc":
            rows.reverse()
        rows = [r for r in rows if r["id"] not in self.deleted and _matches(r, q.get("$filter"))]
        skip, limit = int(q.get("skip", 0)), int(q.get("limit", 10))
        return [self._render(table, r) for r in rows[skip : skip + limit]]

    def _item(self, method: str, table: str, item_id: str, body: dict | None):
        if item_id in self.deleted:
            return 410, {"detail": "deleted", "item_name": self.db[table][item_id].get("name")}
        row = self.db[table].get(item_id)
        if not row:
            return 404, {"detail": "not found"}
        if method == "PUT":
            row.update(self._prepare(table, body))
        return 200, self._render(table, row)

    def _create(self, table: str, body: dict):
        if not body.get("project_id") or body["project_id"] not in self.db["projects"]:
            return 400, {"detail": "invalid project_id"}
        if table == "tests" and body.get("prompt_id", "") not in (*self.db["prompts"], ""):
            return 400, {"detail": "invalid prompt_id"}
        if (
            table == "tests"
            and not body.get("prompt_id")
            and not (body.get("test_configuration") or {}).get("goal")
        ):
            return 422, {"detail": "a test needs a prompt or a multi-turn goal"}
        row = self.insert(table, **self._prepare(table, body))
        return 200, self._render(table, row)

    def _prepare(self, table: str, body: dict) -> dict:
        body = {k: v for k, v in body.items() if v is not None and k not in ("id", "nano_id")}
        if table == "metrics":
            for field in ("metric_type", "backend_type"):
                if field in body:
                    type_name = "MetricType" if field == "metric_type" else "BackendType"
                    body[f"{field}_id"] = self.lookup_id(type_name, body.pop(field))
        if table == "endpoints":
            body["has_auth_token"] = bool(body.pop("auth_token", None))
        return body

    def _ref(self, table: str, ref_id: str | None) -> dict | None:
        row = self.db[table].get(ref_id) if ref_id else None
        # Like the backend, a soft-deleted row is left out of the relationship load.
        if not row or ref_id in self.deleted:
            return None
        return {k: v for k, v in row.items() if k in ("id", "name", "project_id", "description")}

    def _lookup(self, ref_id: str | None) -> dict | None:
        row = self.db["type_lookups"].get(ref_id) if ref_id else None
        return {k: row[k] for k in ("id", "type_name", "type_value")} if row else None

    def _render(self, table: str, row: dict) -> dict:
        out = {k: copy.deepcopy(v) for k, v in row.items() if k != "_seq"}
        if table == "tests":
            prompt = self.db["prompts"].get(row.get("prompt_id"))
            out["prompt"] = (
                {k: v for k, v in prompt.items() if k not in ("_seq", "language_code")}
                if prompt
                else None
            )
            out["topic"] = self._ref("topics", row.get("topic_id"))
            out["category"] = self._ref("categories", row.get("category_id"))
            out["requirement"] = self._ref("requirements", row.get("requirement_id"))
            out["test_type"] = self._lookup(row.get("test_type_id"))
        if table == "requirements":
            out["metrics"] = [
                self._render("metrics", self.db["metrics"][m])
                for r, m in sorted(self.req_metric)
                if r == row["id"]
            ]
            out["impact"] = self._lookup(row.get("impact_id"))
            out["sources"] = [
                {
                    "id": sid,
                    "title": self.db["sources"][sid]["title"],
                    "note": note,
                    "source_type": self._lookup(self.db["sources"][sid].get("source_type_id")),
                }
                for (rid, sid), note in sorted(self.req_source.items())
                if rid == row["id"]
            ]
        if table == "metrics":
            out["metric_type"] = self._lookup(row.get("metric_type_id"))
            out["backend_type"] = self._lookup(row.get("backend_type_id"))
        if table == "test_sets":
            out["test_set_type"] = self._lookup(row.get("test_set_type_id"))
        if table == "sources":
            out.pop("content", None)  # like the API: only the /content route returns it
            out["source_type"] = self._lookup(row.get("source_type_id"))
        if table == "projects":
            out.pop("parameters_schema", None)
        return out

    # ---- link routes ------------------------------------------------------------------------

    def _req_metrics(self, method, q, body, rid):
        return 200, [
            self._render("metrics", self.db["metrics"][m]) for r, m in self.req_metric if r == rid
        ]

    def _parameter_schema(self, method, q, body, pid):
        if not self.has_parameters_api:
            return 404, {"detail": "Not Found"}
        project = self.db["projects"][pid]
        if method == "PUT":
            project["parameters_schema"] = body
        return 200, project.get("parameters_schema") or {"fields": []}

    # ---- experiments and environments --------------------------------------------------------

    def add_experiment(self, project_id: str, name: str, visibility: str = "shared", **kw) -> dict:
        exp = {"id": str(uuid.uuid4()), "project_id": project_id, "name": name,
               "description": kw.get("description"), "visibility": visibility, "versions": [],
               "owner": kw.get("owner", "key-user"), "_seq": next(self._seq)}  # fmt: skip
        self.experiments[exp["id"]] = exp
        return exp

    def add_version(self, exp: dict, values: dict, message: str | None = None) -> dict:
        project = self.db["projects"][exp["project_id"]]
        fields = {f["name"]: f for f in (project.get("parameters_schema") or {}).get("fields", [])}
        typed = {k: v for k, v in values.items() if k in fields}  # unknown fields are dropped
        for name, value in typed.items():
            if isinstance(value, dict) and value.get("type") != fields[name]["type"]:
                raise ValueError(f"{name}: expected {fields[name]['type']}")
        for name, field in fields.items():
            if name not in typed and field.get("default") is not None:
                typed[name] = {"type": field["type"], "value": field["default"]}
        latest = exp["versions"][-1] if exp["versions"] else None
        if latest and latest["values"] == typed:
            return latest  # saving the same values again is a no-op
        version = {"version": f"v{len(exp['versions']) + 1}", "values": typed, "message": message,
                   "parent_version": latest["version"] if latest else None}  # fmt: skip
        exp["versions"].append(version)
        return version

    def _experiment_read(self, exp: dict, detail: bool = False) -> dict:
        out = {k: v for k, v in exp.items() if k not in ("_seq", "versions", "owner")}
        out["versions_count"] = len(exp["versions"])
        out["latest_version"] = exp["versions"][-1]["version"] if exp["versions"] else None
        if detail:
            out["versions"] = copy.deepcopy(exp["versions"])
        return out

    def _project_experiments(self, method, q, body, pid):
        if method == "POST":
            exp = self.add_experiment(pid, body["name"], body.get("visibility", "private"),
                                      description=body.get("description"))  # fmt: skip
            return 201, self._experiment_read(exp)
        rows = sorted((e for e in self.experiments.values() if e["project_id"] == pid),
                      key=lambda e: e["_seq"])  # fmt: skip
        skip, limit = int(q.get("skip", 0)), int(q.get("limit", 100))
        # Like the backend: other users' private experiments are dropped after paging.
        page = [
            e
            for e in rows[skip : skip + limit]
            if e["visibility"] == "shared" or e["owner"] == "key-user"
        ]
        return 200, [self._experiment_read(e) for e in page]

    def _experiment(self, method, q, body, eid):
        exp = self.experiments.get(eid)
        if not exp:
            return 404, {"detail": "not found"}
        if method == "PATCH" and exp["owner"] != "key-user":
            return 403, {"detail": "not the owner"}
        if method == "PATCH":
            pointed = any(
                p and p["experiment_id"] == eid
                for p in self.environments.get(exp["project_id"], {}).values()
            )
            if body.get("visibility") == "private" and pointed:
                return 409, {"detail": "an environment points at this experiment"}
            exp.update({k: v for k, v in body.items() if v is not None})
        return 200, self._experiment_read(exp, detail=True)

    def _experiment_versions(self, method, q, body, eid):
        exp = self.experiments[eid]
        parent = body.get("parent_version")
        if parent and parent not in {v["version"] for v in exp["versions"]} and exp["versions"]:
            return 422, {"detail": f"parent_version {parent!r} does not exist"}
        try:
            return 201, self.add_version(exp, body.get("values") or {}, body.get("message"))
        except ValueError as e:
            return 422, {"detail": str(e)}

    def _environments(self, method, q, body, pid):
        envs = self.environments.setdefault(pid, {})
        if method == "POST":
            name = body["name"]
            if name in envs or name in ("default", "development", "staging", "production"):
                return 409, {"detail": "already exists"}
            envs[name] = None
        return 200, {"environments": copy.deepcopy(envs)}

    def _environment(self, method, q, body, pid, name):
        envs = self.environments.setdefault(pid, {})
        if method == "DELETE":
            if name not in envs:
                return 404, {"detail": "not found"}
            del envs[name]
            return 200, {"environments": copy.deepcopy(envs)}
        exp = self.experiments.get(body["experiment_id"])
        if not exp or exp["visibility"] != "shared":
            return 409, {"detail": "environments point only at shared experiments"}
        if body["version"] not in {v["version"] for v in exp["versions"]}:
            return 404, {"detail": "version not found"}
        envs[name] = {"experiment_id": body["experiment_id"], "version": body["version"]}
        return 200, {"environments": copy.deepcopy(envs)}

    def _source_content(self, method, q, body, sid):
        row = self.db["sources"].get(sid)
        if not row:
            return 404, {"detail": "not found"}
        return 200, {**self._render("sources", row), "content": row.get("content")}

    def _req_source_link(self, method, q, body, rid, sid):
        if method == "DELETE":
            if (rid, sid) not in self.req_source:
                return 404, {"detail": "Source was not linked to this requirement"}
            del self.req_source[(rid, sid)]
        else:
            self.req_source[(rid, sid)] = (body or {}).get("note")
        return 200, {"status": "success"}

    def _disassociate(self, method, q, body, sid):
        self.set_tests[sid] = [t for t in self.set_tests.get(sid, []) if t not in body["test_ids"]]
        return 200, {"ok": True}

    def _req_metric_link(self, method, q, body, rid, mid):
        if method == "DELETE":
            if (rid, mid) not in self.req_metric:
                return 404, {"detail": "not linked"}
            self.req_metric.discard((rid, mid))
            return 200, {"ok": True}
        if (rid, mid) in self.req_metric:
            return 400, {"detail": "already linked"}
        self.req_metric.add((rid, mid))
        return 200, {"ok": True}

    def _set_tests_list(self, method, q, body, sid):
        ids = self.set_tests.get(sid, [])
        skip, limit = int(q.get("skip", 0)), int(q.get("limit", 10))
        return 200, [self._render("tests", self.db["tests"][t]) for t in ids[skip : skip + limit]]

    def _associate(self, method, q, body, sid):
        current = self.set_tests.setdefault(sid, [])
        current.extend(t for t in body["test_ids"] if t not in current)
        return 200, {"ok": True}

    def _set_metrics_list(self, method, q, body, sid):
        return 200, [
            self._render("metrics", self.db["metrics"][m]) for m in self.set_metrics.get(sid, [])
        ]

    def _set_metric_link(self, method, q, body, sid, mid):
        current = self.set_metrics.setdefault(sid, [])
        if method == "DELETE":
            if mid not in current:
                return 404, {"detail": "not linked"}
            current.remove(mid)
            return 200, [self._render("metrics", self.db["metrics"][m]) for m in current]
        if mid in current:
            return 400, {"detail": "already linked"}
        current.append(mid)
        return 200, {"ok": True}


def _matches(row: dict, odata: str | None) -> bool:
    """Enough OData for the tool: `field eq value` clauses joined by `and`."""
    if not odata:
        return True
    for clause in odata.split(" and "):
        field, _, raw = clause.partition(" eq ")
        value = raw[1:-1].replace("''", "'") if raw.startswith("'") else raw
        if str(row.get(field.strip())) != value:
            return False
    return True


class FakeClock:
    def __init__(self):
        self.now = 0.0
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds

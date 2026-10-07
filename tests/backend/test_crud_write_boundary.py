"""CRUD write boundary guard.

Explicit database writes live in the CRUD layer: ``app/crud/``,
``app/utils/crud_utils.py`` and each EE feature's ``crud.py``. Everything else
(routers, services, jobs) calls a CRUD function instead of writing itself.

That keeps every write path in one reviewable place per entity, and keeps bulk
statements as ORM statements that return the ids they touched, so a session
hook can see exactly which rows changed.

What counts as an explicit write
--------------------------------
- ``add``, ``add_all``, ``delete``, ``merge`` and the legacy ``bulk_*`` methods
  on a session (any receiver whose name contains ``db`` or ``session``).
- Legacy ``Query`` bulk writes: ``.update(...)`` or ``.delete()`` on a chain
  that contains ``query``/``filter``/``filter_by``/``where``.
- Statements built with SQLAlchemy's ``insert``/``update``/``delete``, a
  table's ``.insert()``/``.update()``/``.delete()``, or a ``text()`` that starts
  with ``INSERT``/``UPDATE``/``DELETE``/``TRUNCATE``.

Out of scope
------------
- ``commit``/``flush``: who owns the transaction is a separate question, and
  routers and CRUD functions both commit today.
- Setting attributes on a loaded row. That is still an ORM write the session
  flush sees; no static check can tell it apart from building a response.
- Alembic migrations.

``ALLOWED_OFFENDERS`` only shrinks. Adding to it is a regression: move the
write into the entity's CRUD module. The entries left are infrastructure
writes on tables that are not audited as user activity.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

REPO_ROOT = Path(__file__).parents[2]
CORE_SRC = REPO_ROOT / "apps/backend/src/rhesis/backend"
EE_SRC = REPO_ROOT / "ee/backend/src/rhesis/backend/ee"

SESSION_WRITE_METHODS = frozenset(
    {
        "add",
        "add_all",
        "delete",
        "merge",
        "bulk_save_objects",
        "bulk_insert_mappings",
        "bulk_update_mappings",
    }
)
QUERY_CHAIN_METHODS = frozenset({"query", "filter", "filter_by", "where"})
DML_CONSTRUCTORS = frozenset({"insert", "update", "delete"})
TEXT_DML = re.compile(r"\s*(INSERT|UPDATE|DELETE|TRUNCATE)\b", re.IGNORECASE)

_CORE = "apps/backend/src/rhesis/backend"
_EE = "ee/backend/src/rhesis/backend/ee"

#: Paths relative to the repo root, with the reason each may still write.
ALLOWED_OFFENDERS: dict[str, str] = {
    # Infrastructure on tables that are not audited as user activity.
    f"{_CORE}/app/auth/refresh_token_utils.py": "refresh token rotation and cleanup",
    f"{_CORE}/app/services/usage.py": "usage counters, upserted on every metered call",
    f"{_CORE}/events/sinks/activity_log.py": "the activity log sink itself",
    f"{_CORE}/jobs/retention.py": "retention sweep",
    f"{_CORE}/jobs/trace_retention.py": "trace retention sweep",
    f"{_CORE}/jobs/tracking.py": "job status tracking",
    f"{_CORE}/local_init.py": "local development bootstrap",
    # EE writes, moved into ee/<feature>/crud.py separately.
    f"{_EE}/api_clients/router.py": "EE consolidation pending",
    f"{_EE}/rbac/default_role.py": "EE consolidation pending",
    f"{_EE}/rbac/router.py": "EE consolidation pending",
}


def _is_crud_layer(path: Path) -> bool:
    if path.is_relative_to(CORE_SRC / "app" / "crud"):
        return True
    if path == CORE_SRC / "app" / "utils" / "crud_utils.py":
        return True
    return path.is_relative_to(EE_SRC) and path.name == "crud.py"


def _receiver_name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Name):
        return node.id
    return None


def _is_session(node: ast.expr) -> bool:
    name = (_receiver_name(node) or "").lower()
    return "db" in name or "session" in name


def _chain_has_query(node: ast.expr) -> bool:
    if "query" in (_receiver_name(node) or "").lower():
        return True
    while isinstance(node, (ast.Call, ast.Attribute)):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr in QUERY_CHAIN_METHODS:
                return True
            node = func
        else:
            node = node.value
    return False


def _sqlalchemy_dml_names(tree: ast.AST) -> set[str]:
    """Local names bound to sqlalchemy's insert/update/delete constructors."""
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("sqlalchemy"):
            for alias in node.names:
                if alias.name in DML_CONSTRUCTORS:
                    names.add(alias.asname or alias.name)
    return names


def _text_literal(node: ast.expr) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        return "".join(v.value for v in node.values if isinstance(v, ast.Constant))
    return None


def _write_kind(call: ast.Call, dml_names: set[str]) -> str | None:
    func = call.func
    if isinstance(func, ast.Name):
        if func.id in dml_names:
            return func.id
        if func.id == "text" and call.args:
            literal = _text_literal(call.args[0])
            if literal and TEXT_DML.match(literal):
                return "text DML"
        return None
    if not isinstance(func, ast.Attribute):
        return None
    if func.attr in SESSION_WRITE_METHODS and _is_session(func.value):
        return func.attr
    if func.attr in ("update", "delete") and _chain_has_query(func.value):
        return f"query.{func.attr}"
    # table.insert() / table.delete(); list.insert(i, x) always has args.
    if func.attr in DML_CONSTRUCTORS and not call.args and not call.keywords:
        if not _is_session(func.value):
            return f".{func.attr}()"
    return None


def find_writes(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    dml_names = _sqlalchemy_dml_names(tree)
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            kind = _write_kind(node, dml_names)
            if kind:
                found.append(f"line {node.lineno}: {kind}")
    return found


def _source_files() -> list[Path]:
    files = [p for p in CORE_SRC.rglob("*.py") if "alembic" not in p.parts]
    files += list(EE_SRC.rglob("*.py"))
    return sorted(files)


def _offenders() -> dict[str, list[str]]:
    out = {}
    for path in _source_files():
        if _is_crud_layer(path):
            continue
        writes = find_writes(path)
        if writes:
            out[str(path.relative_to(REPO_ROOT))] = writes
    return out


def test_writes_live_in_the_crud_layer() -> None:
    new = {p: w for p, w in _offenders().items() if p not in ALLOWED_OFFENDERS}
    assert not new, (
        "Database writes outside the CRUD layer. Move them into app/crud/<entity>.py "
        "(or ee/<feature>/crud.py) and call that instead:\n\n"
        + "\n".join(f"{p}\n    " + "\n    ".join(w) for p, w in new.items())
    )


def test_bulk_writes_return_their_ids() -> None:
    """Legacy ``Query.update()``/``.delete()`` report a count, never which rows changed.

    Applies inside the CRUD layer too. Use ``crud_utils.bulk_update`` or
    ``bulk_delete``, which return the ids they touched.
    """
    found = {}
    for path in _source_files():
        rel = str(path.relative_to(REPO_ROOT))
        if rel in ALLOWED_OFFENDERS:
            continue
        legacy = [w for w in find_writes(path) if ": query." in w]
        if legacy:
            found[rel] = legacy
    assert not found, "Legacy Query bulk writes:\n\n" + "\n".join(
        f"{p}\n    " + "\n    ".join(w) for p, w in found.items()
    )


def test_allowed_offenders_still_write() -> None:
    """A file that stopped writing comes off the list, so the list only shrinks."""
    offenders = _offenders()
    stale = sorted(p for p in ALLOWED_OFFENDERS if p not in offenders)
    assert not stale, "No longer write outside the CRUD layer; remove from ALLOWED_OFFENDERS:\n" + (
        "\n".join(stale)
    )

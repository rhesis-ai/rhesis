"""Guard against routers returning internal error text to clients.

A broad ``except Exception as e`` that puts ``e`` into ``detail=`` hands the
caller whatever the failure happened to say -- SQLAlchemy statements, OAuth
provider internals, filesystem paths. Narrow handlers (``except ValueError``)
are fine and deliberate: those messages are written for the user to read.

``KNOWN_LEAKS`` is the backlog being worked off in batches. A file's count may
only ever go down. When it hits zero, delete the entry.
"""

import ast
from pathlib import Path

import pytest

ROUTERS_DIR = (
    Path(__file__).resolve().parents[3]
    / "apps"
    / "backend"
    / "src"
    / "rhesis"
    / "backend"
    / "app"
    / "routers"
)

#: Exception types broad enough that their text is of unknown origin.
BROAD_EXCEPTIONS = {"Exception", "BaseException"}

#: file name -> number of leaks still tolerated. Only ever shrinks.
KNOWN_LEAKS: dict[str, int] = {}


def _is_broad(handler: ast.ExceptHandler) -> bool:
    if handler.type is None:  # bare `except:`
        return True
    names = handler.type.elts if isinstance(handler.type, ast.Tuple) else [handler.type]
    return any(isinstance(n, ast.Name) and n.id in BROAD_EXCEPTIONS for n in names)


def _references(node: ast.AST, names: set[str]) -> bool:
    return any(isinstance(n, ast.Name) and n.id in names for n in ast.walk(node))


def _tainted_names(handler: ast.ExceptHandler) -> set[str]:
    """The exception name plus every local it was copied into.

    ``error_msg = str(e)`` then ``detail=f"...{error_msg}"`` is the same leak
    written in two steps, and checking only the exception name misses it.
    Iterates to a fixpoint so chains of copies are caught too.
    """
    tainted = {handler.name}
    while True:
        grown = set(tainted)
        for node in ast.walk(handler):
            if isinstance(node, ast.Assign) and _references(node.value, tainted):
                grown |= {t.id for t in node.targets if isinstance(t, ast.Name)}
            elif (
                isinstance(node, ast.AnnAssign)
                and node.value is not None
                and isinstance(node.target, ast.Name)
                and _references(node.value, tainted)
            ):
                grown.add(node.target.id)
        if grown == tainted:
            return tainted
        tainted = grown


def find_leaks(source: str) -> list[int]:
    """Line numbers where a broad handler feeds its exception into ``detail=``."""
    leaks = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.ExceptHandler) or not _is_broad(node) or not node.name:
            continue
        tainted = _tainted_names(node)
        for inner in ast.walk(node):
            if not isinstance(inner, ast.Call):
                continue
            for kw in inner.keywords:
                if kw.arg == "detail" and _references(kw.value, tainted):
                    leaks.append(inner.lineno)
    return sorted(set(leaks))


def router_files() -> list[Path]:
    return sorted(p for p in ROUTERS_DIR.glob("*.py") if p.name != "__init__.py")


@pytest.mark.parametrize("path", router_files(), ids=lambda p: p.name)
def test_router_does_not_leak_internal_errors(path: Path):
    leaks = find_leaks(path.read_text())
    allowed = KNOWN_LEAKS.get(path.name, 0)

    assert len(leaks) <= allowed, (
        f"{path.name} leaks internal exception text to clients at lines {leaks}. "
        f"Log the exception and return a generic message instead -- see "
        f"rhesis.backend.app.error_handlers.internal_error."
    )

    if len(leaks) < allowed:
        pytest.fail(
            f"{path.name} now has {len(leaks)} leaks, fewer than the allowed {allowed}. "
            f"Lower KNOWN_LEAKS['{path.name}'] to {len(leaks)} "
            f"({'or delete the entry' if len(leaks) == 0 else 'to lock the improvement in'})."
        )


def test_allowlist_has_no_stale_entries():
    """A file listed in KNOWN_LEAKS must still exist."""
    names = {p.name for p in router_files()}
    assert not (set(KNOWN_LEAKS) - names), (
        f"KNOWN_LEAKS names routers that no longer exist: {set(KNOWN_LEAKS) - names}"
    )

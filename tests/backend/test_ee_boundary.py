"""EE boundary guard.

Asserts that no module under ``apps/backend/src/rhesis/backend/`` (the MIT
core) imports, at module level, anything from ``rhesis.backend.ee``. The
only permitted couplings are ``try/except ImportError`` blocks inside
``ee_bootstrap.py`` and ``alembic/env.py`` -- the two boot points where
core needs to detect (and load) optional EE artefacts. A second test
verifies that EE imports in those files are in fact wrapped in a try
block, so a future edit cannot quietly remove the guard.

Why two allowed files?
----------------------
- ``app/ee_bootstrap.py`` mounts EE routers and registers EE features at
  application startup.
- ``alembic/env.py`` eagerly imports EE-owned ORM models so their tables
  join ``Base.metadata`` before ``alembic upgrade`` configures the
  migration context. Without this, autogenerate would not see EE tables
  and an offline upgrade from a fresh DB would leave them missing.

Both are part of the boot infrastructure, both must work in
Community-only deployments where the EE package is absent, both wrap
their imports in ``try/except ImportError``.

Why a static AST check?
----------------------
A runtime import test would need a working app environment. The boundary
is structural, not behavioural, so source analysis is faster and cheaper:
the test runs in milliseconds and needs only Python plus pytest.

Limits
------
The check flags **all static imports** in a file -- including those inside
function or method bodies -- because ``ast.walk`` traverses the entire AST.
Dynamic imports (``importlib.import_module``, ``__import__``) are
intentionally out of scope; the goal is a fast guard against the common
mistake, not an exhaustive import tracker.
"""

from __future__ import annotations

import ast
from pathlib import Path

# Root of the MIT-licensed core source tree.
CORE_SRC = Path(__file__).parents[2] / "apps/backend/src/rhesis/backend"

# The only files allowed to reference rhesis.backend.ee, each via a
# try/except guard. See module docstring for the rationale of each entry.
ALLOWED_FILES = frozenset(
    {
        (CORE_SRC / "app" / "ee_bootstrap.py").resolve(),
        (CORE_SRC / "alembic" / "env.py").resolve(),
    }
)

EE_MARKER = "rhesis.backend.ee"


def _imported_modules(tree: ast.AST) -> list[tuple[int, str]]:
    """Return ``(lineno, module_name)`` for every Import / ImportFrom in *tree*."""
    out: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                out.append((node.lineno, alias.name))
        elif isinstance(node, ast.ImportFrom) and node.module:
            out.append((node.lineno, node.module))
    return out


def _try_block_line_ranges(tree: ast.AST) -> list[tuple[int, int]]:
    """Return ``(start_lineno, end_lineno)`` for every ast.Try in *tree*."""
    ranges: list[tuple[int, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Try):
            end = max(
                (getattr(n, "end_lineno", node.lineno) for n in ast.walk(node)),
                default=node.lineno,
            )
            ranges.append((node.lineno, end))
    return ranges


def test_core_does_not_import_ee() -> None:
    """No core module (except those in ALLOWED_FILES) may import rhesis.backend.ee."""
    violations: list[str] = []

    for py_file in sorted(CORE_SRC.rglob("*.py")):
        if py_file.resolve() in ALLOWED_FILES:
            continue

        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
        except SyntaxError:
            continue

        for _, name in _imported_modules(tree):
            if name == EE_MARKER or name.startswith(f"{EE_MARKER}."):
                rel = py_file.relative_to(CORE_SRC.parents[3])
                violations.append(f"{rel}: imports '{name}'")

    assert not violations, (
        "Core modules must not import from rhesis.backend.ee.\n"
        "Move EE-only code to ee/backend/ or use one of the boot-point\n"
        "files in ALLOWED_FILES (ee_bootstrap.py, alembic/env.py).\n\n"
        + "\n".join(violations)
    )


def test_allowed_files_wrap_ee_imports_in_try_except() -> None:
    """Every EE import in an ALLOWED_FILES module must be try/except-guarded.

    The hard requirement is that ``rhesis.backend.ee`` imports do not
    crash Community-mode startup or migration when the package is
    missing. Wrapping them in ``try/except ImportError`` is what makes
    the no-op behaviour possible.
    """
    for allowed in sorted(ALLOWED_FILES):
        tree = ast.parse(allowed.read_text(encoding="utf-8"))
        try_ranges = _try_block_line_ranges(tree)

        for lineno, name in _imported_modules(tree):
            if name != EE_MARKER and not name.startswith(f"{EE_MARKER}."):
                continue
            inside_try = any(start <= lineno <= end for start, end in try_ranges)
            assert inside_try, (
                f"{allowed.name} line {lineno}: '{name}' is imported outside "
                "a try/except block. Wrap it so Community mode doesn't "
                "hard-fail."
            )

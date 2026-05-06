"""EE boundary guard.

Asserts that no module under ``apps/backend/src/rhesis/backend/`` (the MIT
core) imports, at module level, anything from ``rhesis.backend.ee``. The
only permitted coupling is the ``try/except ImportError`` inside
``ee_bootstrap.py``. A second test verifies that the EE import in
``ee_bootstrap.py`` is in fact wrapped in a try block — so a future
edit cannot quietly remove the guard.

Why a static AST check?
----------------------
A runtime import test would need a working app environment. The boundary
is structural, not behavioural, so source analysis is faster and cheaper:
the test runs in milliseconds and needs only Python plus pytest.

Limits
------
The check catches **module-level** imports only. A function-body import
(``from rhesis.backend.ee import x`` inside a function) would not be
flagged. That pattern would still violate the architectural rule, but
it is also a code smell on its own; CODEOWNERS review on ``apps/backend/``
is the secondary line of defence. Catching dynamic imports
(``importlib.import_module``, ``__import__``) is intentionally out of
scope — the goal is a fast guard against the common mistake.
"""

from __future__ import annotations

import ast
from pathlib import Path

# Root of the MIT-licensed core source tree.
CORE_SRC = Path(__file__).parents[2] / "apps/backend/src/rhesis/backend"

# The only file allowed to reference rhesis.backend.ee (via try/except).
ALLOWED_FILE = CORE_SRC / "app" / "ee_bootstrap.py"

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
    """No core module (except ee_bootstrap.py) may import rhesis.backend.ee."""
    violations: list[str] = []

    for py_file in sorted(CORE_SRC.rglob("*.py")):
        if py_file.resolve() == ALLOWED_FILE.resolve():
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
        "Move EE-only code to ee/backend/ or use ee_bootstrap.py.\n\n" + "\n".join(violations)
    )


def test_ee_bootstrap_is_try_except_only() -> None:
    """ee_bootstrap.py may only reference EE inside a try/except block.

    The hard requirement is that ``rhesis.backend.ee`` imports do not
    crash Community-mode startup when the package is missing. Wrapping
    them in ``try/except ImportError`` is what makes the no-op behaviour
    possible.
    """
    tree = ast.parse(ALLOWED_FILE.read_text(encoding="utf-8"))
    try_ranges = _try_block_line_ranges(tree)

    for lineno, name in _imported_modules(tree):
        if name != EE_MARKER and not name.startswith(f"{EE_MARKER}."):
            continue
        inside_try = any(start <= lineno <= end for start, end in try_ranges)
        assert inside_try, (
            f"ee_bootstrap.py line {lineno}: '{name}' is imported outside a "
            "try/except block. Wrap it so Community mode doesn't hard-fail."
        )

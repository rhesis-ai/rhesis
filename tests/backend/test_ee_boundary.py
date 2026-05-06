"""EE boundary guard.

Asserts that no module under ``apps/backend/src/rhesis/backend/`` (the MIT
core) imports, at module level, anything from ``rhesis.backend.ee``.

The only permitted coupling is the ``try/except ImportError`` inside
``ee_bootstrap.py``. If this test fails on a commit that doesn't touch
``ee_bootstrap.py``, a core module has gained a hard dependency on EE code
and the "delete ee/ → pure MIT build" guarantee is broken.

This test is fast and runs without a running database because it works purely
on source text. It is intentionally run in the Community CI job
(``backend-test-community``) where the ``ee`` extra is NOT installed.
"""

from __future__ import annotations

import ast
from pathlib import Path

# Root of the MIT-licensed core source tree.
CORE_SRC = Path(__file__).parents[2] / "apps/backend/src/rhesis/backend"

# The only file allowed to reference rhesis.backend.ee (via try/except).
ALLOWED_FILE = CORE_SRC / "app" / "ee_bootstrap.py"

EE_MARKER = "rhesis.backend.ee"


def _top_level_imports(path: Path) -> list[str]:
    """Return all names imported at module level in *path*."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:
        return []

    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                names.append(node.module)
    return names


def test_core_does_not_import_ee() -> None:
    """No core module (except ee_bootstrap.py) may import rhesis.backend.ee."""
    violations: list[str] = []

    for py_file in sorted(CORE_SRC.rglob("*.py")):
        if py_file.resolve() == ALLOWED_FILE.resolve():
            continue

        for name in _top_level_imports(py_file):
            if name.startswith(EE_MARKER) or name == EE_MARKER:
                rel = py_file.relative_to(CORE_SRC.parents[3])
                violations.append(f"{rel}: imports '{name}'")

    assert not violations, (
        "Core modules must not import from rhesis.backend.ee.\n"
        "Move EE-only code to ee/backend/ or use ee_bootstrap.py.\n\n"
        + "\n".join(violations)
    )


def test_ee_bootstrap_is_try_except_only() -> None:
    """ee_bootstrap.py must only reference EE via a try/except ImportError block.

    This ensures the import is guarded and won't hard-fail in Community mode
    where the ``ee`` extra is not installed.
    """
    source = ALLOWED_FILE.read_text(encoding="utf-8")
    tree = ast.parse(source)

    bare_ee_imports: list[str] = []

    for node in ast.walk(tree):
        # We're looking for ImportFrom/Import nodes that reference EE
        # but are NOT inside a Try node.
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            mod = ""
            if isinstance(node, ast.ImportFrom) and node.module:
                mod = node.module
            elif isinstance(node, ast.Import):
                mod = ",".join(a.name for a in node.names)

            if mod.startswith(EE_MARKER):
                # Check if this node sits inside a Try block by looking at
                # the source line and whether it's inside a try/except.
                # Simple heuristic: walk Try nodes and collect their lineno ranges.
                bare_ee_imports.append(mod)

    # Verify all EE imports are inside try blocks.
    try_ranges: list[tuple[int, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Try):
            end = max(
                (getattr(n, "end_lineno", node.lineno) for n in ast.walk(node)),
                default=node.lineno,
            )
            try_ranges.append((node.lineno, end))

    for node in ast.walk(tree):
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        mod = ""
        if isinstance(node, ast.ImportFrom) and node.module:
            mod = node.module
        elif isinstance(node, ast.Import):
            mod = ",".join(a.name for a in node.names)

        if not mod.startswith(EE_MARKER):
            continue

        lineno = node.lineno
        inside_try = any(start <= lineno <= end for start, end in try_ranges)
        assert inside_try, (
            f"ee_bootstrap.py line {lineno}: '{mod}' is imported outside a "
            "try/except block. Wrap it so Community mode doesn't hard-fail."
        )

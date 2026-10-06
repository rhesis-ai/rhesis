"""No user-facing model error is built from a caught exception's text.

``ModelConfigurationError`` messages are shown to users, and ``model_setup_message``
passes them on unchanged because they are our own wording. A provider's exception text
can quote the rejected request, API key included, so it must never be interpolated into
one. The caught exception belongs on ``original_error``.

Source-text check, like ``test_ee_boundary.py``: it flags an f-string message that
interpolates an ``except ... as`` name, or ``str()`` / ``repr()`` of one.
"""

from __future__ import annotations

import ast
from pathlib import Path

BACKEND_SRC = Path(__file__).parents[2] / "apps/backend/src/rhesis/backend"
_GUARDED = {"ModelConfigurationError"}


def _called_name(call: ast.Call) -> str | None:
    if isinstance(call.func, ast.Name):
        return call.func.id
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return None


def _interpolated_names(message: ast.expr) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(message):
        if not isinstance(node, ast.FormattedValue):
            continue
        value = node.value
        if isinstance(value, ast.Call) and _called_name(value) in {"str", "repr"} and value.args:
            value = value.args[0]
        if isinstance(value, ast.Name):
            names.add(value.id)
    return names


def _violations(path: Path) -> list[tuple[int, list[str]]]:
    tree = ast.parse(path.read_text(), filename=str(path))
    found = []
    for handler in ast.walk(tree):
        if not isinstance(handler, ast.ExceptHandler) or not handler.name:
            continue
        # error_msg = str(e) is the same text under another name.
        caught = {handler.name}
        for node in ast.walk(handler):
            if (
                isinstance(node, ast.Assign)
                and isinstance(node.value, ast.Call)
                and _called_name(node.value) in {"str", "repr"}
                and any(isinstance(a, ast.Name) and a.id in caught for a in node.value.args)
            ):
                caught |= {t.id for t in node.targets if isinstance(t, ast.Name)}
        for node in ast.walk(handler):
            if not (isinstance(node, ast.Call) and _called_name(node) in _GUARDED and node.args):
                continue
            leaked = _interpolated_names(node.args[0]) & caught
            if leaked:
                found.append((node.lineno, sorted(leaked)))
    return found


def test_no_model_configuration_error_quotes_a_caught_exception():
    violations = [
        f"{path.relative_to(BACKEND_SRC.parents[3])}:{line} interpolates {names}"
        for path in BACKEND_SRC.rglob("*.py")
        for line, names in _violations(path)
    ]
    assert not violations, "\n".join(violations)


def test_the_check_catches_a_leak(tmp_path):
    """Guards the guard: it has to flag the patterns it exists for."""
    sample = tmp_path / "sample.py"
    sample.write_text(
        "def f():\n"
        "    try:\n"
        "        pass\n"
        "    except ValueError as e:\n"
        "        error_msg = str(e)\n"
        "        raise ModelConfigurationError(f'failed: {e}')\n"
        "        raise ModelConfigurationError(f'failed: {error_msg}')\n"
        "        raise ModelConfigurationError(f'failed: {str(e)}')\n"
    )
    assert len(_violations(sample)) == 3

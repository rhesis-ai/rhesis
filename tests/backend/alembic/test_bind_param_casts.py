"""Guard against `:param::type` inside ``text()`` SQL.

SQLAlchemy's bind-parameter scanner skips any ``:name`` immediately followed
by another ``:``. That rule exists so PostgreSQL's ``::`` cast syntax survives
untouched, but it cannot tell the ``x`` in ``a::b`` apart from a parameter the
author meant to bind. So ``text("... ANY(:ids::uuid[])")`` compiles with **zero**
bind parameters, the params dict is silently dropped, and the literal string
``:ids::uuid[]`` reaches the server -- which rejects it with
``syntax error at or near ":"``.

Nothing catches this at author time: ``text()`` accepts the string and
``.compile()`` succeeds. It only fails when the statement runs, which is why one
instance broke ~6300 backend tests in a single CI run and two others sat
unnoticed in downgrade paths that CI never exercises.

The fix is always ``CAST(:x AS type)``.

Why a static AST check?
-----------------------
The bug is in the SQL string, not in runtime behaviour, so reading the source is
enough -- no database, no app environment, milliseconds to run. Scoping to
``text()`` call arguments (rather than grepping every string) keeps unrelated
``::`` text out of it, such as the IPv6 literals in the EE SSO client.

Limits
------
Only string literals written directly inside a ``text()`` call are checked,
including implicitly concatenated ones. SQL assembled in a variable first, or
built by f-string or ``.format()``, is out of scope; the goal is a fast guard
against the common mistake, not an exhaustive SQL analyser.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

REPO_ROOT = Path(__file__).parents[3]

# Directories whose Python sources may build SQL through text().
SEARCH_ROOTS = ("apps", "sdk", "ee", "scripts", "tests")

# A bind parameter glued to a PostgreSQL cast: the `::` swallows the parameter.
BAD_CAST = re.compile(r":[a-zA-Z_][a-zA-Z0-9_]*::")


def _is_text_call(node: ast.AST) -> bool:
    """True for `text(...)` and any attribute form such as `sa.text(...)`."""
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if isinstance(func, ast.Name):
        return func.id == "text"
    return isinstance(func, ast.Attribute) and func.attr == "text"


def _string_parts(node: ast.AST) -> list[str]:
    """Collect literal string pieces, following implicit concatenation."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value]
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return _string_parts(node.left) + _string_parts(node.right)
    return []


def _python_files() -> list[Path]:
    files: list[Path] = []
    for root in SEARCH_ROOTS:
        base = REPO_ROOT / root
        if base.is_dir():
            files.extend(p for p in base.rglob("*.py") if ".venv" not in p.parts)
    return files


def _offenders() -> list[str]:
    """Return `path:line: sql` for every text() call with a glued cast."""
    found: list[str] = []
    for path in _python_files():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            if not _is_text_call(node):
                continue
            for arg in node.args:
                sql = "".join(_string_parts(arg))
                if BAD_CAST.search(sql):
                    rel = path.relative_to(REPO_ROOT)
                    found.append(f"{rel}:{node.lineno}: {sql}")
    return found


def test_no_bind_param_glued_to_cast():
    """No text() SQL binds a parameter directly onto a `::` cast."""
    offenders = _offenders()
    assert not offenders, (
        "Bind parameter glued to a `::` cast — SQLAlchemy will not bind it and "
        "PostgreSQL will reject the literal. Use CAST(:x AS type) instead:\n  "
        + "\n  ".join(offenders)
    )


def test_guard_detects_a_known_bad_pattern():
    """The matcher itself catches the shape it is meant to catch."""
    assert BAD_CAST.search("DELETE FROM model WHERE id = ANY(:ids::uuid[])")
    assert not BAD_CAST.search("DELETE FROM model WHERE id = ANY(CAST(:ids AS uuid[]))")
    # A cast with no bind parameter in front of it is ordinary PostgreSQL.
    assert not BAD_CAST.search("SELECT now()::date")


def test_guard_relies_on_ast_scoping_not_the_regex():
    """The regex alone is not selective enough; restricting it to text() args is.

    An IPv6 literal such as ``fd00:ec2::254`` matches the pattern, so a bare grep
    over the repo reports the EE SSO client. Those strings are never arguments to
    ``text()``, which is why the scan walks the AST instead.
    """
    assert BAD_CAST.search("fd00:ec2::254")
    assert not _is_text_call(ast.parse("requests.get('fd00:ec2::254')").body[0].value)

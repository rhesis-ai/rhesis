"""Static guard against ``==`` on secret-shaped variables.

Comparing two values with ``==`` is a timing oracle whenever one side
is a secret (a token, a hash, a password, a client secret).
``hmac.compare_digest`` does the same check in constant time. This
test walks the backend source tree and fails if it finds an ``==``
or ``!=`` whose left or right operand is identifier-shaped and ends
in (or contains) one of the sensitive markers below.

Why a separate test rather than a ruff rule?
--------------------------------------------
Ruff has ``S105`` ("hard-coded password") but no rule for "comparing
two variables that look like secrets". We could push for a custom
ruff rule, but a 60-line AST walk is faster to land, easier to audit,
and runs as part of the existing ``tests/backend/`` suite -- which we
already gate the build on.

Tradeoffs / scope limits
------------------------
- Identifier matching is name-based: a variable spelled ``stored_hash``
  flags, ``stored_value`` does not. Project convention is to name
  these vars sensibly (``token_hash``, ``client_secret``); the
  guard's value comes from being noisy when the convention is
  followed.
- Only ``==`` and ``!=`` are checked. Comparison via ``in``,
  ``startswith``, etc. is not (those have their own timing profile
  but are vanishingly rare for secrets).
- Tests in ``tests/`` are skipped: assertion-style equality on
  secrets is fine in unit tests because the inputs are fixtures, not
  attacker-controlled.
- A handful of constructs are pre-approved (see ``ALLOWED_SITES``)
  for legitimate non-secret comparisons whose variable names happen
  to match. Each entry needs a code comment explaining why it is
  safe.
"""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# Roots scanned by this guard. Adjust if the project layout grows.
SCAN_ROOTS = (
    REPO_ROOT / "apps" / "backend" / "src",
    REPO_ROOT / "ee" / "backend" / "src",
)

# Substrings (case-insensitive) that mark an identifier as
# "secret-shaped". Conservative on purpose: a false positive is a
# 30-second rename in the calling code, a false negative is a
# silent timing oracle in production.
SENSITIVE_MARKERS = (
    "_secret",
    "_hash",
    "_token",
    "password",
    "passwd",
    "pwd",
)

# (file_relative_to_repo, lineno) sites that are allowed despite the
# heuristic. Add an entry only with a one-line comment justifying why
# the comparison is timing-safe (e.g. "compares to a public string
# constant", "compares to None", "compares hash *prefix* by length").
ALLOWED_SITES: frozenset[tuple[str, int]] = frozenset(
    {
        # content_hash is a SHA-based fingerprint for version dedup, not a secret
        ("apps/backend/src/rhesis/backend/app/services/experiment.py", 155),
        ("apps/backend/src/rhesis/backend/app/services/experiment.py", 211),
    }
)


def _is_sensitive_name(name: str) -> bool:
    """Return True if *name* contains one of the secret markers."""
    lower = name.lower()
    return any(marker in lower for marker in SENSITIVE_MARKERS)


def _operand_name(node: ast.expr) -> str | None:
    """Return the leaf identifier of a Name / Attribute operand, else ``None``.

    Subscripts (``foo[bar]``), calls (``foo()``), and other shapes
    return ``None`` -- the heuristic only fires on plain identifier
    comparisons because those are what the timing-oracle pattern
    looks like.
    """
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        # Walk to the leaf attribute; ``foo.bar.token_hash`` -> "token_hash".
        return node.attr
    return None


def _is_class_attribute(node: ast.expr) -> bool:
    """Return True when *node* is ``ClassName.attr`` (Capitalized parent).

    Walks the dotted chain and returns True if the *immediate parent*
    of the leaf attribute is either:

    - a ``Name`` whose identifier is Capitalized
      (e.g. ``RefreshToken.token_hash``), or
    - an ``Attribute`` whose ``attr`` is Capitalized
      (e.g. ``models.Token.token_hash``).

    Both shapes indicate a SQLAlchemy column comparison or an enum
    member access, neither of which is a runtime secret comparison.
    Without this we'd flood with false positives from CRUD modules
    full of ``WHERE`` clauses on hash columns.
    """
    if not isinstance(node, ast.Attribute):
        return False
    parent = node.value
    if isinstance(parent, ast.Name):
        return parent.id[:1].isupper()
    if isinstance(parent, ast.Attribute):
        return parent.attr[:1].isupper()
    return False


def _is_module_constant(node: ast.expr) -> bool:
    """Return True for a bare UPPER_SNAKE name (module-level constant).

    A comparison against a module constant (e.g. ``aud !=
    RHESIS_TOKEN_AUDIENCE``) is not a secret comparison -- the
    constant is in the source tree by definition.
    """
    return (
        isinstance(node, ast.Name)
        and node.id.isupper()
        and "_" in node.id
    )


def _is_safe_other_side(node: ast.expr) -> bool:
    """Return True when *node* is a "safe" operand for an equality test.

    Safe means: comparing against this operand does not produce a
    timing oracle on the other operand because the operand is either
    a literal, a class attribute (SQL or enum), or a module constant.
    """
    if isinstance(node, ast.Constant):
        return True
    if _is_class_attribute(node):
        return True
    if _is_module_constant(node):
        return True
    return False


def _flag_compare(node: ast.Compare) -> bool:
    """Return True when *node* is a sensitive-looking equality compare."""

    has_eq_or_neq = any(
        isinstance(op, (ast.Eq, ast.NotEq)) for op in node.ops
    )
    if not has_eq_or_neq:
        return False

    operands: list[ast.expr] = [node.left, *node.comparators]

    # If any operand is itself a class-attribute or module constant,
    # the whole comparison is treated as safe: an SQL WHERE clause
    # or constant comparison cannot leak a runtime secret on its own.
    if any(_is_safe_other_side(op) for op in operands):
        return False

    operand_names = [_operand_name(op) for op in operands]
    sensitive = [name for name in operand_names if name and _is_sensitive_name(name)]
    if not sensitive:
        return False

    # At this point we have at least one sensitive-shaped operand and
    # neither side is "safe" (a constant, class attribute, or module
    # constant). That is the timing-oracle pattern.
    return True


def test_no_naive_equality_on_secrets() -> None:
    """Every ``==`` comparing two secret-shaped names must be hmac.compare_digest."""

    violations: list[str] = []

    for root in SCAN_ROOTS:
        if not root.exists():
            continue
        for py_file in sorted(root.rglob("*.py")):
            # Tests can use plain == for fixture comparisons.
            if "/tests/" in str(py_file).replace("\\", "/"):
                continue
            try:
                tree = ast.parse(py_file.read_text(encoding="utf-8"))
            except SyntaxError:
                continue
            rel = py_file.relative_to(REPO_ROOT)
            for node in ast.walk(tree):
                if not isinstance(node, ast.Compare):
                    continue
                if (str(rel), node.lineno) in ALLOWED_SITES:
                    continue
                if _flag_compare(node):
                    snippet = ast.unparse(node)
                    violations.append(f"{rel}:{node.lineno}: {snippet}")

    assert not violations, (
        "Secret-shaped variables compared with == or != -- use "
        "hmac.compare_digest for constant-time comparison.\n\n"
        "If a flagged site is genuinely safe (e.g. comparing a hash "
        "prefix to a constant), add it to ALLOWED_SITES with a "
        "one-line justification.\n\n" + "\n".join(violations)
    )

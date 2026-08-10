"""Language models are constructed in one place, so accrual can't be skipped.

Before this test existed, roughly a dozen call sites across the backend
built a language model straight from ``get_model()`` -- most commonly to
unwrap a string that ``get_user_generation_model()`` returns when the org
has no model configured. Each one was an unstamped model: no record of
whose credentials paid for it, so it fell back to the process-wide sink's
"unstamped" heuristic instead of being definitively attributed.

The fix was to consolidate that unwrap into
``user_model_utils.ensure_language_model()``, which stamps. This test is
what keeps it consolidated: it fails the moment a new call site imports the
SDK factory directly instead of going through the resolution layer, rather
than relying on someone noticing an ``usage.unstamped_model`` log line in
production.

Embedding construction is deliberately exempt -- ``BaseEmbedder`` has no
usage-emission path at all, so there is nothing for it to skip.
"""

from __future__ import annotations

import ast
from pathlib import Path

import rhesis.backend

_BACKEND_SRC = Path(rhesis.backend.__file__).parent

_LANGUAGE_MODEL_FACTORY_NAMES = {"get_model", "get_language_model"}

#: Files allowed to import the SDK's language-model factory directly.
#: Adding to this list should be rare and deliberate -- see the module
#: docstring on why this list exists and does not want to grow.
_ALLOWED_IMPORTERS = {
    # The resolution layer itself: every stamp in the codebase lives here,
    # including `ensure_language_model`, the one sanctioned unwrap point.
    "app/utils/user_model_utils.py",
    # Per-metric judge model override. Stamps directly via
    # `stamp_usage_provenance`, mirroring `_is_hosted_model` at the call site.
    "metrics/strategies/local.py",
    # Relays a generation call for a self-hosted deployment / SaaS loopback.
    # Stamps directly (system default -- see the function's docstring) and
    # also constructs an embedder (exempt) in the same module.
    "app/routers/services.py",
    # Embedding construction: BaseEmbedder never emits usage, so there is no
    # accrual decision for these to skip.
    "app/services/embedding/generator.py",
    "app/services/embedding/graph_builder.py",
    "app/services/explorer/embeddings.py",
    # Connection tests run a real generation against credentials the user
    # just typed into the form. Stamped `metered=False` explicitly -- these
    # tokens are never ours to bill, so ensure_language_model's `metered=True`
    # default would be wrong here, not just redundant.
    "app/services/model_connection.py",
}


def _imports_language_model_factory(tree: ast.Module) -> bool:
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.ImportFrom)
            and node.module
            and node.module.startswith("rhesis.sdk.models")
        ):
            if any(alias.name in _LANGUAGE_MODEL_FACTORY_NAMES for alias in node.names):
                return True
    return False


def _offending_files():
    for path in _BACKEND_SRC.rglob("*.py"):
        relative = str(path.relative_to(_BACKEND_SRC))
        if relative in _ALLOWED_IMPORTERS:
            continue
        tree = ast.parse(path.read_text(), filename=str(path))
        if _imports_language_model_factory(tree):
            yield relative


def test_only_the_resolution_layer_constructs_language_models():
    offenders = sorted(_offending_files())
    assert not offenders, (
        f"{offenders} import the SDK language-model factory directly. A model "
        f"built this way carries no usage-provenance stamp, so its tokens fall "
        f"back to the process-wide sink's heuristic instead of being properly "
        f"attributed. Resolve the model via "
        f"rhesis.backend.app.utils.user_model_utils (e.g. "
        f"ensure_language_model() to unwrap a get_user_*_model() string) "
        f"instead, or add the file to _ALLOWED_IMPORTERS here with a comment "
        f"explaining why it is exempt."
    )


def test_the_allowlist_contains_no_stale_entries():
    """A file that no longer imports the factory should come off the list,
    so the allowlist stays a true record of where construction happens."""
    stale = [
        relative
        for relative in _ALLOWED_IMPORTERS
        if not _imports_language_model_factory(ast.parse((_BACKEND_SRC / relative).read_text()))
    ]
    assert not stale, f"{stale} no longer import the factory; remove from _ALLOWED_IMPORTERS"

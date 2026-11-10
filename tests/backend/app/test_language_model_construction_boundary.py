"""Language models are constructed in one place, so accrual can't be skipped.

Before this test existed, roughly a dozen call sites across the backend
built a language model straight from ``get_model()`` -- most commonly to
unwrap a bare provider string that model resolution used to hand back.
Each one was an unstamped model: no record of whose credentials paid for
it, so it fell back to the process-wide sink's "unstamped" heuristic
instead of being definitively attributed.

The fix landed in two steps. First the unwrap was consolidated into
``user_model_utils.ensure_language_model()``, which stamps. Then
``resolve_model()`` stopped handing back strings at all, so there is
nothing left for a caller to unwrap. This test is what keeps it that way:
it fails the moment a new call site imports the SDK factory directly
instead of going through the resolution layer, rather than relying on
someone noticing an ``usage.unstamped_model`` log line in production.

Embedding construction would be exempt -- ``BaseEmbedder`` has no
usage-emission path at all -- but ``resolve_embedder()`` means no module
outside the resolution layer builds one either.
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
    # Connection tests run a real generation against credentials the user
    # just typed into the form. Stamped `metered=False` explicitly -- these
    # tokens are never ours to bill, so ensure_language_model's `metered=True`
    # default would be wrong here, not just redundant.
    "app/services/model_connection.py",
}


#: Modules that expose the factory as an attribute. Importing one of these
#: wholesale is the other way to reach ``get_model``
#: (``import rhesis.sdk.models.factory as f`` then ``f.get_model(...)``), so
#: the import itself is what gets flagged. Catching the *import* rather than
#: the attribute access keeps this free of false positives -- ``crud`` has
#: its own unrelated ``get_model``, and matching on the attribute name alone
#: would flag every call to it.
_FACTORY_MODULES = {"rhesis.sdk.models", "rhesis.sdk.models.factory"}


def _imports_language_model_factory(tree: ast.Module) -> bool:
    for node in ast.walk(tree):
        # from rhesis.sdk.models[.factory] import get_model
        if (
            isinstance(node, ast.ImportFrom)
            and node.module
            and node.module.startswith("rhesis.sdk.models")
        ):
            if any(alias.name in _LANGUAGE_MODEL_FACTORY_NAMES for alias in node.names):
                return True
        # import rhesis.sdk.models[.factory] [as f]
        if isinstance(node, ast.Import):
            if any(alias.name in _FACTORY_MODULES for alias in node.names):
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


# The second way to skip the gate: hand a ``DEFAULT_*_MODEL`` string straight to an
# SDK class (``MetricSynthesizer(model=get_model_settings().generation_model)``). The
# SDK builds it itself, so it is never stamped and never checked against MODEL_TOKENS.

_DEFAULT_MODEL_SETTINGS = {
    "generation_model",
    "evaluation_model",
    "execution_model",
    "embedding_model",
}

#: Callables a default-model setting may be handed to: they gate on the quota.
_GATED_WRAPPERS = {"resolve_default_hosted_model"}

#: Files allowed to read a default-model setting outside a gated wrapper.
_DEFAULT_SETTING_READERS = {
    # The resolution layer itself.
    "app/utils/user_model_utils.py",
    # Compares the default's provider; builds nothing from it.
    "app/services/model_connection.py",
    # Polyphemus-user fallbacks behind the route-level TEST_GENERATION gate.
    "app/services/test_config_generator.py",
    "app/services/test_generation_pipeline.py",
}


def _is_default_setting(node: ast.AST) -> bool:
    """``get_model_settings().<purpose>_model``."""
    return (
        isinstance(node, ast.Attribute)
        and node.attr in _DEFAULT_MODEL_SETTINGS
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name)
        and node.value.func.id == "get_model_settings"
    )


def _call_name(call: ast.Call) -> str | None:
    if isinstance(call.func, ast.Name):
        return call.func.id
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return None


def _ungated_default_setting_reads(tree: ast.Module) -> list[int]:
    gated = {
        id(arg)
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and _call_name(node) in _GATED_WRAPPERS
        for arg in [*node.args, *(kw.value for kw in node.keywords)]
    }
    return [
        node.lineno
        for node in ast.walk(tree)
        if _is_default_setting(node) and id(node) not in gated
    ]


def _default_setting_offenders(source_by_file):
    for relative, source in source_by_file:
        if relative.startswith("app/config/") or relative in _DEFAULT_SETTING_READERS:
            continue
        for line in _ungated_default_setting_reads(ast.parse(source)):
            yield f"{relative}:{line}"


def _backend_sources():
    for path in _BACKEND_SRC.rglob("*.py"):
        yield str(path.relative_to(_BACKEND_SRC)), path.read_text()


def test_default_models_are_only_built_through_the_quota_gate():
    offenders = sorted(_default_setting_offenders(_backend_sources()))
    assert not offenders, (
        f"{offenders} read a DEFAULT_*_MODEL setting outside resolve_default_hosted_model(). "
        f"Handing that string to an SDK class builds an unstamped model that never checks "
        f"the MODEL_TOKENS quota. Pass resolve_default_hosted_model(setting, db, org_id) instead."
    )


def test_the_default_setting_gate_catches_a_string_handed_to_an_sdk_class():
    bad = (
        "synthesizer = MetricSynthesizer(model=get_model_settings().generation_model)\n"
        "model = get_model_settings().generation_model\n"
    )
    good = "m = resolve_default_hosted_model(get_model_settings().generation_model, db, org)\n"
    assert sorted(_default_setting_offenders([("app/routers/x.py", bad)])) == [
        "app/routers/x.py:1",
        "app/routers/x.py:2",
    ]
    assert list(_default_setting_offenders([("app/routers/x.py", good)])) == []

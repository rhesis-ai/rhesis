"""The ``rhesis.sdk.telemetry`` re-export shims stay usable and stay in sync.

``attributes``, ``context`` and ``token_extraction`` moved into the lightweight ``rhesis`` package
(#2462) so framework integrations can depend on ``rhesis[telemetry]`` instead of the whole SDK.
Every import site in this repository now uses the canonical ``rhesis.telemetry.*`` paths (#2473),
which means nothing here exercises the old paths any more — and a compatibility surface no test
touches is one that breaks silently.

What breaks if these fail: released ``rhesis-haystack`` versions import
``rhesis.sdk.telemetry.attributes`` and ``rhesis.sdk.telemetry.context``, and so does any user code
written before the move.
"""

import importlib

import pytest
from rhesis.telemetry import attributes as canonical_attributes
from rhesis.telemetry import context as canonical_context
from rhesis.telemetry import token_extraction as canonical_token_extraction

SHIMS = [
    ("rhesis.sdk.telemetry.attributes", canonical_attributes),
    ("rhesis.sdk.telemetry.context", canonical_context),
    ("rhesis.sdk.telemetry.utils.token_extraction", canonical_token_extraction),
]


@pytest.mark.parametrize("legacy_path, canonical", SHIMS, ids=lambda v: getattr(v, "__name__", v))
def test_shim_re_exports_the_same_objects(legacy_path, canonical):
    """Each name the shim advertises resolves to the canonical object, not a copy of it."""
    legacy = importlib.import_module(legacy_path)

    assert legacy.__all__, f"{legacy_path} advertises nothing"
    for name in legacy.__all__:
        assert getattr(legacy, name) is getattr(canonical, name), (
            f"{legacy_path}.{name} is not {canonical.__name__}.{name}"
        )


@pytest.mark.parametrize("legacy_path, canonical", SHIMS, ids=lambda v: getattr(v, "__name__", v))
def test_shim_forwards_the_whole_canonical_surface(legacy_path, canonical):
    """The shim forwards exactly what the canonical module declares public, no more and no less.

    Compared against the canonical ``__all__`` rather than inferred from the module namespace,
    because inference cannot answer the question. Filtering ``vars()`` by ``__module__`` catches
    functions and classes but silently drops constants — ``MAX_CONTENT_LENGTH`` is an ``int`` and
    carries no ``__module__`` — while dropping the underscore-prefixed names would keep imports the
    module makes for its own use, like ``FORBIDDEN_SPAN_DOMAINS`` from ``schemas``. Either way a new
    public constant could be added to a canonical module and skip the shim unnoticed.

    A failure here is a decision to make, not a line to delete: a name added to the canonical
    module either belongs on the old path too, or the shim deliberately stops short and this test
    should say so.
    """
    legacy = importlib.import_module(legacy_path)

    missing = set(canonical.__all__) - set(legacy.__all__)
    extra = set(legacy.__all__) - set(canonical.__all__)
    assert not missing, f"{legacy_path} does not forward {sorted(missing)}"
    assert not extra, (
        f"{legacy_path} advertises {sorted(extra)}, which {canonical.__name__} does not"
    )


def test_context_vars_are_shared_across_both_paths():
    """The ContextVars live in one module, so a write through either path is visible from the other.

    This is what lets the SDK and a framework integration read the same turn state while importing
    from different paths. A shim that rebound its own ContextVars would pass the identity tests
    above and still split the state in two.
    """
    legacy = importlib.import_module("rhesis.sdk.telemetry.context")

    legacy.set_root_trace_id("cafe" * 8)
    try:
        assert canonical_context.get_root_trace_id() == "cafe" * 8

        canonical_context.set_conversation_id("conv-1")
        assert legacy.get_conversation_id() == "conv-1"
    finally:
        legacy.set_root_trace_id(None)
        canonical_context.set_conversation_id(None)


def test_legacy_utils_package_still_exports_token_extraction():
    """``rhesis.sdk.telemetry.utils`` published ``extract_token_usage``; it still does.

    This is the one place in the repository that still imports a legacy telemetry path, and it does
    so deliberately: the module *is* the old public surface.
    """
    utils = importlib.import_module("rhesis.sdk.telemetry.utils")

    assert utils.extract_token_usage is canonical_token_extraction.extract_token_usage

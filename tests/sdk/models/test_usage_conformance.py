"""Every registered language provider must report its token usage.

Two providers shipped without emitting anything -- ``LiteLLMProxy`` parsed
the response and threw the ``usage`` field away, and ``HuggingFaceLLM``
computed exact counts and stored them on an unused attribute. Neither
failed any test, because emission was a per-provider obligation that lived
only in docstrings. Nobody noticed until someone went looking at a usage
dashboard and found a hosted provider reporting zero forever.

The registry is the thing that grows, so the registry is what gets checked:
adding a provider whose emission nobody has covered fails here.
"""

from __future__ import annotations

import inspect

import pytest

from rhesis.sdk.models.base import BaseLLM
from rhesis.sdk.models.factory import UNIFIED_MODEL_REGISTRY, ModelType, _ProviderSpec

#: Direct ``BaseLLM`` subclasses whose emission is covered by a real test.
#: Everything else in the registry inherits its generate methods from one of
#: these, so covering the roots covers the tree.
#:
#: Adding a name here means committing to a test that drives the provider's
#: transport and asserts ``on_usage`` fires -- see the ``covered by`` note on
#: each. Do not add one to make this test pass.
COVERED_EMISSION_ROOTS = {
    "LiteLLM",  # covered by tests/sdk/models/providers/test_litellm.py
    "RhesisLLM",  # covered by tests/sdk/models/providers/test_rhesis.py
    "PolyphemusLLM",  # covered by tests/sdk/models/providers/test_polyphemus.py
    "LiteLLMProxy",  # covered by tests/sdk/models/providers/test_litellm_proxy.py
    "HuggingFaceLLM",  # covered by tests/sdk/models/providers/test_hugginface.py
}

#: Providers whose class cannot be imported without optional heavy deps.
_OPTIONAL_DEPS = {"huggingface"}


def _language_providers():
    for provider, by_type in UNIFIED_MODEL_REGISTRY.items():
        factory = by_type.get(ModelType.LANGUAGE)
        if factory is not None:
            yield provider, factory


def _provider_class(factory):
    """Resolve a registry entry to its provider class.

    Entries are either a ``_ProviderSpec`` (module + class name, imported
    lazily) or a plain callable wrapper -- Vertex AI uses the latter because
    it takes no api_key. For a wrapper, read the class out of the annotated
    return type's module by finding the single BaseLLM subclass it imports.
    """
    if isinstance(factory, _ProviderSpec):
        import importlib

        return getattr(importlib.import_module(factory.module), factory.class_name)

    # Callable wrapper: pull the class from the function's own source module.
    source = inspect.getsource(factory)
    for line in source.splitlines():
        line = line.strip()
        if line.startswith("from ") and " import " in line:
            module_path, _, names = line.partition(" import ")
            import importlib

            module = importlib.import_module(module_path[len("from ") :])
            for name in names.split(","):
                candidate = getattr(module, name.strip(), None)
                if isinstance(candidate, type) and issubclass(candidate, BaseLLM):
                    return candidate
    raise AssertionError(f"could not resolve a provider class from {factory!r}")


def _emission_root(cls):
    """The direct ``BaseLLM`` subclass *cls* inherits its behaviour from."""
    for base in cls.__mro__:
        if BaseLLM in base.__bases__:
            return base
    raise AssertionError(f"{cls.__name__} does not descend from BaseLLM")


@pytest.mark.parametrize("provider,factory", list(_language_providers()))
def test_provider_emission_is_covered(provider, factory):
    if provider in _OPTIONAL_DEPS:
        pytest.importorskip("torch", reason=f"{provider} needs optional deps")

    cls = _provider_class(factory)
    root = _emission_root(cls)

    assert root.__name__ in COVERED_EMISSION_ROOTS, (
        f"'{provider}' resolves to {cls.__name__}, a new emission root "
        f"({root.__name__}) with no usage-emission test. Every language "
        f"provider must call self._emit_usage(...) with its raw usage payload "
        f"-- otherwise its tokens are silently never billed. Add a test "
        f"driving its transport, then list it in COVERED_EMISSION_ROOTS."
    )


@pytest.mark.parametrize("provider,factory", list(_language_providers()))
def test_provider_does_not_bypass_emission_by_overriding_generate(provider, factory):
    """A subclass may override a generate method, but then it owns emission.

    Catches the ``LiteLLMProxy`` shape: inherit from a provider that emits,
    override ``generate`` with a fresh implementation, and silently lose it.
    An override is fine if it emits itself or delegates to something that
    does.
    """
    if provider in _OPTIONAL_DEPS:
        pytest.importorskip("torch", reason=f"{provider} needs optional deps")

    cls = _provider_class(factory)
    root = _emission_root(cls)

    for name in ("generate", "a_generate", "generate_batch"):
        for klass in cls.__mro__:
            if name not in klass.__dict__:
                continue
            if klass is BaseLLM or klass is root:
                break  # base or already-covered root implementation
            source = inspect.getsource(klass.__dict__[name])
            delegates = "super()" in source or "self.generate" in source
            assert "_emit_usage" in source or delegates, (
                f"{klass.__name__}.{name} (provider '{provider}') overrides a "
                f"generate method without emitting usage or delegating to "
                f"something that does, so its tokens go uncounted."
            )
            break


def test_the_covered_roots_all_actually_emit():
    """Guards the allowlist itself: a name in COVERED_EMISSION_ROOTS whose
    module no longer calls _emit_usage means the allowlist went stale."""
    roots = {_emission_root(_provider_class(f)) for _, f in _language_providers()}
    for root in roots:
        source = inspect.getsource(inspect.getmodule(root))
        assert "_emit_usage" in source, (
            f"{root.__name__} is listed as a covered emission root but its "
            f"module never calls _emit_usage"
        )

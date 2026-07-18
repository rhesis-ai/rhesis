"""Install sys.meta_path stubs for the SDK's heavy optional dependencies.

The ``rhesis.backend.tasks`` package eagerly imports ``embedding``,
``endpoint``, ``execution``, ``example_task``, etc. Each of those
transitively pulls in ``rhesis.backend.metrics`` → ``rhesis.sdk.metrics``
→ ``ragas`` / ``deepeval`` / ``langchain_core`` / ... — a
deep tree of optional SDK deps that aren't installed in the lightweight
backend test venv.

The pure data-transformation functions under test (``build_summary_data``,
``get_test_run_project_id``, ``_build_task_result``) don't actually call
into any of these — so stubbing the missing modules lets the import chain
complete without forcing a full SDK install (torch, langchain, etc.) just
to run a unit test.

``litellm`` is intentionally NOT stubbed even though the SDK's metrics
module imports it: litellm IS installed in the backend test venv (it's a
direct dependency of ``rhesis.backend``), and stubbing it leaks into
every other test in the session via ``sys.meta_path`` — the dummy class
returned by the stub is missing real litellm's
``LiteLLMProxyChatConfig._should_use_litellm_proxy_by_default`` attribute,
which causes unrelated ``tests/backend/services/telemetry/test_enrichment.py``
tests to fail with ``AttributeError``. Only truly-absent deps are stubbed.

Usage:
    Just import this module at the top of a test file:

        from tests.backend.tasks._heavy_import_stubs import _  # noqa: F401

    The import has the side effect of installing the meta path finder.

Design notes:
    A ``sys.meta_path`` finder is used rather than a static
    ``sys.modules`` stub list because the SDK's lazy ``__getattr__``
    import pattern pulls in new submodules at runtime (e.g.
    ``ragas.llms``, ``deepeval.test_case``). The finder catches every
    ``ModuleNotFoundError`` for the known-heavy dependency trees and
    returns a stub module whose ``__getattr__`` yields dummy classes,
    so ``from ragas.metrics import AnswerAccuracy`` resolves whether or
    not the real ``ragas`` package is installed.
"""

import importlib.abc
import importlib.machinery
import sys
import types

# Top-level packages (and dotted prefixes) we're willing to stub.
# Anything starting with one of these prefixes will be stubbed on first
# import. Rhesis's own packages (``rhesis.backend``, ``rhesis.sdk``) are
# NOT in this list — those must come from the real source tree.
_STUBBABLE_PREFIXES = (
    "ragas",
    "deepeval",
    "deepteam",
    "langchain",
    "langchain_core",
    "langchain_google_genai",
)


class _StubModule(types.ModuleType):
    """Module stub that returns dummy attributes for any name access."""

    # Mark as a package so ``from <stub>.submod import X`` resolves to a
    # stub child instead of triggering a real filesystem search.
    __path__: list = []

    def __getattr__(self, name):
        # Return a dummy class so ``class Foo(StubbedClass):`` style
        # imports (if any) also don't crash. Instantiations are never
        # reached because the functions under test don't invoke metric
        # code paths.
        return type(name, (), {})


class _StubLoader(importlib.abc.Loader):
    def create_module(self, spec):
        return _StubModule(spec.name)

    def exec_module(self, module):
        # No-op: the stub is fully populated by ``__getattr__`` at
        # attribute-access time. We don't need to execute any real code.
        pass


class _StubFinder(importlib.abc.MetaPathFinder):
    """Meta path finder that returns stub loaders for heavy deps.

    Only matches modules whose dotted name starts with one of
    ``_STUBBABLE_PREFIXES``. Other imports fall through to the standard
    finders, so genuine ``ModuleNotFoundError`` (e.g. a typo'd rhesis
    module) still surfaces.

    Even when a prefix matches, the finder FIRST defers to
    ``importlib.machinery.PathFinder.find_spec()`` to check whether the
    real package is actually installed on ``sys.path``. Only when the
    real package truly isn't available does it return a stub ``ModuleSpec``.
    This prevents the stub from shadowing a real install — without this
    check, inserting the finder at ``sys.meta_path[0]`` would stub
    ``langchain``/``langchain_core``/etc. even in venvs where those
    packages are present, and the dummy ``_StubModule.__getattr__`` class
    would leak into every other test in the same pytest session (see peqy
    review rev_01KY3T1YY0NK0SC81Z3BZH8XFD, and the ``litellm`` write-up
    above for the failure mode this guards against).
    """

    def find_spec(self, fullname, path, target=None):
        if not any(
            fullname == prefix or fullname.startswith(prefix + ".")
            for prefix in _STUBBABLE_PREFIXES
        ):
            return None
        # Defer to the standard path finder FIRST. If the real package is
        # installed on sys.path, return None so the import machinery falls
        # through to the standard finders and resolves to the genuine module.
        # ``PathFinder.find_spec`` is a static method that walks sys.path
        # directly (it doesn't recurse into sys.meta_path), so this won't
        # re-enter our finder.
        real_spec = importlib.machinery.PathFinder.find_spec(fullname, path)
        if real_spec is not None:
            return None
        # Real package truly isn't available — stub it so the SDK's eager
        # import chain completes without forcing a full install of
        # torch/langchain/ragas just to run a unit test.
        return importlib.machinery.ModuleSpec(
            fullname,
            _StubLoader(),
            is_package=True,
        )


# Insert at the front of sys.meta_path so we get first crack at every
# import. ``find_spec`` only stubs modules whose prefix is in
# ``_STUBBABLE_PREFIXES`` AND whose real package can't be found via
# ``PathFinder.find_spec()`` — so inserting at the front is safe even
# for stubbable prefixes that ARE installed (the check short-circuits
# and lets the standard finders handle them normally).
#
# Idempotent: skip if already installed (e.g. when multiple test modules
# import this stub helper in the same session).
if not any(isinstance(f, _StubFinder) for f in sys.meta_path):
    sys.meta_path.insert(0, _StubFinder())

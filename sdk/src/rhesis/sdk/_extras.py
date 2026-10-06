"""Turn a missing ``rhesis-sdk[all]`` package into one install hint."""

import importlib.util
from contextlib import contextmanager
from typing import Iterator

# Top-level import names of the packages that only ship with ``rhesis-sdk[all]``.
FULL_SDK_MODULES = frozenset(
    {
        "chonkie",
        "deepeval",
        "deepteam",
        "httpx",
        "litellm",
        "markitdown",
        "mcp",
        "pdfminer",
        "tiktoken",
    }
)

INSTALL_DOCS_URL = "https://docs.rhesis.ai/sdk/installation#what-to-install"


def full_sdk_message(feature: str) -> str:
    """The one message every guarded import raises."""
    return (
        f"{feature} needs the full SDK. Install it with:\n"
        '    pip install "rhesis-sdk[all]"\n'
        f"See {INSTALL_DOCS_URL}"
    )


class FullSDKRequiredError(ModuleNotFoundError):
    """A feature was used whose packages come only with ``rhesis-sdk[all]``."""


def _is_missing_full_sdk_module(exc: ModuleNotFoundError) -> bool:
    if not exc.name:
        return False
    root = exc.name.partition(".")[0]
    if root not in FULL_SDK_MODULES:
        return False
    # The package itself must be absent: a missing submodule of an installed
    # package is a version problem, and its real error is more useful.
    try:
        return importlib.util.find_spec(root) is None
    except (ImportError, ValueError):
        return False


@contextmanager
def requires_full_sdk(feature: str) -> Iterator[None]:
    """Re-raise a missing ``[all]`` package as :class:`FullSDKRequiredError`.

    Any other ImportError, including one from our own modules, passes through.
    When guards nest, the outermost feature name wins.
    """
    try:
        yield
    except ModuleNotFoundError as exc:
        if not _is_missing_full_sdk_module(exc):
            raise
        cause = exc.__cause__ if isinstance(exc, FullSDKRequiredError) else exc
        raise FullSDKRequiredError(full_sdk_message(feature), name=exc.name) from cause

"""Services: document extraction and related utilities. Heavy modules load on first access."""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rhesis.sdk.services.extractor import DocumentExtractor

_LAZY_EXPORTS: dict[str, tuple[str, str]] = {
    "DocumentExtractor": ("rhesis.sdk.services.extractor", "DocumentExtractor"),
}


def __getattr__(name: str):
    spec = _LAZY_EXPORTS.get(name)
    if spec is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr_name = spec
    mod = importlib.import_module(module_name)
    return getattr(mod, attr_name)


def __dir__() -> list[str]:
    return sorted(__all__)


__all__ = [
    "DocumentExtractor",
]

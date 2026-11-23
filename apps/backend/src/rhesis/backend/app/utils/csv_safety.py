"""Spreadsheet-safe CSV cells."""

from typing import Any

# A cell starting with one of these runs as a formula in a spreadsheet (OWASP CSV injection).
FORMULA_START = ("=", "+", "-", "@", "\t", "\r")


def _looks_like_formula(text: str) -> bool:
    return text.startswith(FORMULA_START) or text.lstrip().startswith(FORMULA_START)


def neutralize_formula(value: Any) -> Any:
    """Prefix a string a spreadsheet would run as a formula with ``'``; anything else is kept.

    Leading whitespace is looked past too, since some importers trim it first.
    """
    if isinstance(value, str) and _looks_like_formula(value):
        return f"'{value}"
    return value


def restore_formula(value: Any) -> Any:
    """Undo :func:`neutralize_formula`, so an exported CSV imports unchanged."""
    if isinstance(value, str) and value.startswith("'") and _looks_like_formula(value[1:]):
        return value[1:]
    return value

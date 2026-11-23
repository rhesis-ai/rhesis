"""Spreadsheet-safe CSV cells."""

from typing import Any

# A cell starting with one of these runs as a formula in a spreadsheet (OWASP CSV injection).
FORMULA_START = ("=", "+", "-", "@", "\t", "\r")


def neutralize_formula(value: Any) -> Any:
    """Prefix a string a spreadsheet would run as a formula with ``'``; anything else is kept.

    Leading whitespace is looked past too, since some importers trim it first.
    """
    if isinstance(value, str) and (
        value.startswith(FORMULA_START) or value.lstrip().startswith(FORMULA_START)
    ):
        return f"'{value}"
    return value

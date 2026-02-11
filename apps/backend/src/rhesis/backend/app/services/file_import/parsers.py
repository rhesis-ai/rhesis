"""File parsers for import.

Reads uploaded files and returns raw row dictionaries.
Delegates to the SDK's normalization logic where possible.
"""

import csv
import io
import json
from typing import Any, Dict, List, Tuple

from rhesis.backend.logging import logger

# Maximum sample rows returned during the analyze step
MAX_SAMPLE_ROWS = 5


def detect_format(filename: str) -> str:
    """Detect file format from the filename extension.

    Returns one of: json, jsonl, csv, xlsx
    Raises ValueError for unsupported formats.
    """
    lower = filename.lower()
    if lower.endswith(".jsonl"):
        return "jsonl"
    if lower.endswith(".json"):
        return "json"
    if lower.endswith(".csv"):
        return "csv"
    if lower.endswith(".xlsx") or lower.endswith(".xls"):
        return "xlsx"
    raise ValueError(
        f"Unsupported file format: {filename}. Supported formats: .json, .jsonl, .csv, .xlsx, .xls"
    )


def parse_file(
    file_bytes: bytes,
    file_format: str,
) -> List[Dict[str, Any]]:
    """Parse file bytes into a list of raw row dictionaries.

    Args:
        file_bytes: Raw file content.
        file_format: One of json, jsonl, csv, xlsx.

    Returns:
        List of dictionaries, one per row/entry.
    """
    if file_format == "json":
        return _parse_json(file_bytes)
    if file_format == "jsonl":
        return _parse_jsonl(file_bytes)
    if file_format == "csv":
        return _parse_csv(file_bytes)
    if file_format == "xlsx":
        return _parse_xlsx(file_bytes)
    raise ValueError(f"Unsupported format: {file_format}")


def extract_headers_and_sample(
    file_bytes: bytes,
    file_format: str,
    max_rows: int = MAX_SAMPLE_ROWS,
) -> Tuple[List[str], List[Dict[str, Any]]]:
    """Read just the headers and first N rows for the analyze step.

    For structured formats (JSON/JSONL) with nested objects, headers
    are derived from flattened top-level keys of the first entry.

    Returns:
        (headers, sample_rows)
    """
    rows = parse_file(file_bytes, file_format)
    if not rows:
        return [], []

    # Collect all unique keys across sample rows (preserving order)
    sample = rows[:max_rows]
    seen_keys: Dict[str, None] = {}
    for row in sample:
        for key in row:
            if key not in seen_keys:
                seen_keys[key] = None
    headers = list(seen_keys.keys())

    return headers, sample


# ── Internal parsers ─────────────────────────────────────────────


def _parse_json(file_bytes: bytes) -> List[Dict[str, Any]]:
    """Parse JSON data – array, object with 'tests' key, or single object."""
    text = file_bytes.decode("utf-8")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse JSON: {e}") from e

    if isinstance(data, list):
        return [entry for entry in data if isinstance(entry, dict)]

    if isinstance(data, dict):
        # Check for a top-level "tests" array
        if "tests" in data and isinstance(data["tests"], list):
            return [entry for entry in data["tests"] if isinstance(entry, dict)]
        # Single object
        return [data]

    raise ValueError(
        "JSON file must contain an array, an object with a 'tests' key, or a single object"
    )


def _parse_jsonl(file_bytes: bytes) -> List[Dict[str, Any]]:
    """Parse newline-delimited JSON (one object per line)."""
    text = file_bytes.decode("utf-8")
    rows: List[Dict[str, Any]] = []
    for line_num, line in enumerate(text.splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
            if isinstance(entry, dict):
                rows.append(entry)
        except json.JSONDecodeError:
            logger.warning(f"Skipping invalid JSON on line {line_num}")
    return rows


def _parse_csv(file_bytes: bytes) -> List[Dict[str, Any]]:
    """Parse CSV with header row.  Handles BOM encoding."""
    # Try utf-8-sig first (handles BOM), fall back to utf-8
    try:
        text = file_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = file_bytes.decode("utf-8")

    reader = csv.DictReader(io.StringIO(text))
    return [dict(row) for row in reader]


def _parse_xlsx(file_bytes: bytes) -> List[Dict[str, Any]]:
    """Parse Excel file using fastxlsx, returning rows as dicts."""
    try:
        import fastxlsx
    except ImportError as exc:
        raise ImportError(
            "fastxlsx is required for Excel import. Install it with: pip install fastxlsx"
        ) from exc

    wb = fastxlsx.read_xlsx(file_bytes)
    sheet_names = wb.sheet_names
    if not sheet_names:
        return []

    # Use the first sheet
    sheet = wb[sheet_names[0]]
    data = sheet.to_dict_list()
    # fastxlsx returns list of dicts with header row as keys
    return data

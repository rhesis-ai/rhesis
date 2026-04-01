"""Tests for file_import.parsers module."""

import csv
import io
import json

import pytest

from rhesis.backend.app.services.file_import.parsers import (
    detect_format,
    extract_headers_and_sample,
    parse_file,
)


def _make_xlsx_bytes(sheets: dict) -> bytes:
    """Build an xlsx file in memory.

    Args:
        sheets: {sheet_name: [row_tuples]}.  First row of each sheet is
                treated as the header row.
    """
    from openpyxl import Workbook

    wb = Workbook()
    first = True
    for sheet_name, rows in sheets.items():
        if first:
            ws = wb.active
            ws.title = sheet_name
            first = False
        else:
            ws = wb.create_sheet(title=sheet_name)
        for row in rows:
            ws.append(list(row))
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ── detect_format ────────────────────────────────────────────────


class TestDetectFormat:
    def test_json_extension(self):
        assert detect_format("tests.json") == "json"

    def test_jsonl_extension(self):
        assert detect_format("tests.jsonl") == "jsonl"

    def test_csv_extension(self):
        assert detect_format("tests.csv") == "csv"

    def test_xlsx_extension(self):
        assert detect_format("tests.xlsx") == "xlsx"

    def test_xls_extension(self):
        assert detect_format("tests.xls") == "xlsx"

    def test_case_insensitive(self):
        assert detect_format("TESTS.JSON") == "json"
        assert detect_format("data.CSV") == "csv"
        assert detect_format("data.Jsonl") == "jsonl"

    def test_unsupported_format(self):
        with pytest.raises(ValueError, match="Unsupported"):
            detect_format("tests.txt")

    def test_no_extension(self):
        with pytest.raises(ValueError, match="Unsupported"):
            detect_format("no_extension")


# ── JSON parsing ─────────────────────────────────────────────────


class TestParseJson:
    def test_parse_json_list(self):
        data = [{"category": "Safety", "prompt": {"content": "test"}}]
        file_bytes = json.dumps(data).encode("utf-8")
        rows = parse_file(file_bytes, "json")
        assert len(rows) == 1
        assert rows[0]["category"] == "Safety"

    def test_parse_json_object_with_tests_key(self):
        data = {
            "tests": [
                {"category": "Security", "topic": "Auth"},
                {"category": "Safety", "topic": "Content"},
            ]
        }
        file_bytes = json.dumps(data).encode("utf-8")
        rows = parse_file(file_bytes, "json")
        assert len(rows) == 2
        assert rows[0]["category"] == "Security"

    def test_parse_json_single_object(self):
        data = {"category": "Safety", "topic": "Content"}
        file_bytes = json.dumps(data).encode("utf-8")
        rows = parse_file(file_bytes, "json")
        assert len(rows) == 1
        assert rows[0]["category"] == "Safety"

    def test_parse_json_empty_list(self):
        file_bytes = json.dumps([]).encode("utf-8")
        rows = parse_file(file_bytes, "json")
        assert len(rows) == 0

    def test_parse_json_invalid(self):
        with pytest.raises(ValueError, match="Failed to parse"):
            parse_file(b"not json", "json")


# ── JSONL parsing ────────────────────────────────────────────────


class TestParseJsonl:
    def test_parse_jsonl(self):
        lines = [
            json.dumps({"category": "Safety"}),
            json.dumps({"category": "Security"}),
        ]
        file_bytes = "\n".join(lines).encode("utf-8")
        rows = parse_file(file_bytes, "jsonl")
        assert len(rows) == 2

    def test_parse_jsonl_with_blank_lines(self):
        lines = [
            json.dumps({"category": "Safety"}),
            "",
            json.dumps({"category": "Security"}),
            "",
        ]
        file_bytes = "\n".join(lines).encode("utf-8")
        rows = parse_file(file_bytes, "jsonl")
        assert len(rows) == 2

    def test_parse_jsonl_empty(self):
        rows = parse_file(b"", "jsonl")
        assert len(rows) == 0


# ── CSV parsing ──────────────────────────────────────────────────


class TestParseCsv:
    def _make_csv_bytes(self, rows, headers=None):
        buf = io.StringIO()
        if headers:
            writer = csv.DictWriter(buf, fieldnames=headers)
            writer.writeheader()
            for row in rows:
                writer.writerow(row)
        return buf.getvalue().encode("utf-8")

    def test_parse_csv(self):
        headers = ["category", "topic", "prompt"]
        rows = [
            {"category": "Safety", "topic": "Content", "prompt": "hi"},
            {"category": "Security", "topic": "Auth", "prompt": "test"},
        ]
        file_bytes = self._make_csv_bytes(rows, headers)
        result = parse_file(file_bytes, "csv")
        assert len(result) == 2
        assert result[0]["category"] == "Safety"

    def test_parse_csv_empty(self):
        file_bytes = b"category,topic\n"
        result = parse_file(file_bytes, "csv")
        assert len(result) == 0


# ── extract_headers_and_sample ───────────────────────────────────


class TestExtractHeadersAndSample:
    def test_extract_from_json(self):
        data = [
            {"category": "Safety", "topic": "T1", "prompt": "test"},
            {"category": "Security", "topic": "T2", "prompt": "test2"},
        ]
        file_bytes = json.dumps(data).encode("utf-8")
        headers, sample = extract_headers_and_sample(file_bytes, "json")
        assert "category" in headers
        assert "topic" in headers
        assert len(sample) <= 5

    def test_extract_from_csv(self):
        csv_content = "category,topic,prompt\nSafety,Content,hi\n"
        file_bytes = csv_content.encode("utf-8")
        headers, sample = extract_headers_and_sample(file_bytes, "csv")
        assert headers == ["category", "topic", "prompt"]
        assert len(sample) == 1

    def test_extract_sample_limit(self):
        data = [{"x": i} for i in range(100)]
        file_bytes = json.dumps(data).encode("utf-8")
        headers, sample = extract_headers_and_sample(file_bytes, "json")
        assert len(sample) <= 5


# ── XLSX parsing ──────────────────────────────────────────────────


class TestParseXlsx:
    def test_basic_xlsx(self):
        file_bytes = _make_xlsx_bytes(
            {
                "Sheet1": [
                    ("category", "topic", "goal"),
                    ("Safety", "Content", "Test goal"),
                    ("Security", "Auth", "Another goal"),
                ]
            }
        )
        rows = parse_file(file_bytes, "xlsx")
        assert len(rows) == 2
        assert rows[0]["category"] == "Safety"
        assert rows[1]["goal"] == "Another goal"

    def test_blank_first_row_skipped(self):
        """Header row is found even when the first spreadsheet row is blank."""
        file_bytes = _make_xlsx_bytes(
            {
                "Sheet1": [
                    (None, None, None),  # blank first row
                    ("category", "topic", "goal"),
                    ("Safety", "Content", "Test goal"),
                ]
            }
        )
        rows = parse_file(file_bytes, "xlsx")
        assert len(rows) == 1
        assert rows[0]["category"] == "Safety"
        assert rows[0]["goal"] == "Test goal"

    def test_empty_trailing_rows_skipped(self):
        file_bytes = _make_xlsx_bytes(
            {
                "Sheet1": [
                    ("category", "topic"),
                    ("Safety", "Content"),
                    (None, None),
                    ("", ""),
                ]
            }
        )
        rows = parse_file(file_bytes, "xlsx")
        assert len(rows) == 1
        assert rows[0]["category"] == "Safety"

    def test_empty_middle_rows_skipped(self):
        file_bytes = _make_xlsx_bytes(
            {
                "Sheet1": [
                    ("category", "topic"),
                    ("Safety", "Content"),
                    (None, None),
                    ("Security", "Auth"),
                ]
            }
        )
        rows = parse_file(file_bytes, "xlsx")
        assert len(rows) == 2

    def test_multi_sheet_falls_back_to_data_sheet(self):
        """If the active (first) sheet is empty, data is found on the second sheet."""
        file_bytes = _make_xlsx_bytes(
            {
                "Empty": [],  # no data
                "Data": [
                    ("category", "topic", "goal"),
                    ("Safety", "Content", "Test goal"),
                ],
            }
        )
        rows = parse_file(file_bytes, "xlsx")
        assert len(rows) == 1
        assert rows[0]["category"] == "Safety"

    def test_empty_xlsx_returns_empty_list(self):
        file_bytes = _make_xlsx_bytes({"Sheet1": []})
        rows = parse_file(file_bytes, "xlsx")
        assert rows == []

    def test_headers_only_returns_empty_list(self):
        file_bytes = _make_xlsx_bytes({"Sheet1": [("category", "topic")]})
        rows = parse_file(file_bytes, "xlsx")
        assert rows == []

    def test_none_header_cells_skipped(self):
        """Columns with None headers are excluded from all rows."""
        file_bytes = _make_xlsx_bytes(
            {
                "Sheet1": [
                    ("category", None, "topic"),
                    ("Safety", "ignored", "Content"),
                ]
            }
        )
        rows = parse_file(file_bytes, "xlsx")
        assert len(rows) == 1
        assert "category" in rows[0]
        assert "topic" in rows[0]
        assert None not in rows[0]


# ── CSV: empty rows ───────────────────────────────────────────────


class TestParseCsvEmptyRows:
    def test_empty_data_rows_skipped(self):
        csv_content = "category,topic\nSafety,Content\n,,\n\nSecurity,Auth\n"
        rows = parse_file(csv_content.encode("utf-8"), "csv")
        assert len(rows) == 2
        assert rows[0]["category"] == "Safety"
        assert rows[1]["category"] == "Security"

    def test_trailing_empty_rows_skipped(self):
        csv_content = "category,topic\nSafety,Content\n\n\n"
        rows = parse_file(csv_content.encode("utf-8"), "csv")
        assert len(rows) == 1

    def test_semicolon_delimiter(self):
        csv_content = "category;topic\nSafety;Content\n"
        rows = parse_file(csv_content.encode("utf-8"), "csv")
        assert len(rows) == 1
        assert rows[0]["category"] == "Safety"

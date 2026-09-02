"""
Negative / fuzz tests for document_ingest parsers (WI-2, Guardian finding C2).

These verify the parsers fail safely on malformed, oversized, or hostile input
rather than raising unexpected exceptions or exhausting resources.
"""
from __future__ import annotations

import os

import pytest

from forge.document_ingest.cost_parser import (
    parse_cost_usage,
    DocumentTooLargeError,
    MAX_FILE_SIZE_BYTES,
)
from forge.document_ingest.config_parser import parse_config_export


def _write(tmp_path, name, content, mode="w"):
    p = tmp_path / name
    if mode == "wb":
        p.write_bytes(content)
    else:
        p.write_text(content)
    return str(p)


class TestFileSizeCap:
    def test_oversized_csv_rejected(self, tmp_path, monkeypatch):
        # Shrink the cap so we don't have to write 100MB.
        monkeypatch.setattr(
            "forge.document_ingest.cost_parser.MAX_FILE_SIZE_BYTES", 1024
        )
        path = _write(tmp_path, "big.csv", "service,cost\n" + ("x" * 5000))
        with pytest.raises(DocumentTooLargeError):
            parse_cost_usage(path)

    def test_oversized_config_rejected(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "forge.document_ingest.cost_parser.MAX_FILE_SIZE_BYTES", 1024
        )
        path = _write(tmp_path, "big.txt", "y" * 5000)
        with pytest.raises(DocumentTooLargeError):
            parse_config_export(path)


class TestMalformedCsv:
    def test_empty_csv_returns_empty(self, tmp_path):
        path = _write(tmp_path, "empty.csv", "")
        assert parse_cost_usage(path) == []

    def test_header_only_csv_returns_empty(self, tmp_path):
        path = _write(tmp_path, "hdr.csv", "service,cost\n")
        assert parse_cost_usage(path) == []

    def test_no_recognizable_columns(self, tmp_path):
        path = _write(tmp_path, "junk.csv", "foo,bar,baz\n1,2,3\n")
        # No service column → empty list, no exception
        assert parse_cost_usage(path) == []

    def test_ragged_rows_do_not_crash(self, tmp_path):
        content = "sku_name,list_cost_usd\nSQL Warehouse\nJobs Compute,100\n,,,,\n"
        path = _write(tmp_path, "ragged.csv", content)
        # Should parse what it can without raising.
        result = parse_cost_usage(path)
        assert isinstance(result, list)

    def test_non_numeric_cost_ignored(self, tmp_path):
        content = "sku_name,list_cost_usd\nSQL Warehouse,not-a-number\n"
        path = _write(tmp_path, "bad_cost.csv", content)
        result = parse_cost_usage(path)
        assert isinstance(result, list)


class TestHostileBytes:
    def test_binary_garbage_csv(self, tmp_path):
        path = _write(tmp_path, "garbage.csv", bytes(range(256)) * 10, mode="wb")
        # utf-8-sig decode with a reader may raise UnicodeDecodeError; the parser
        # should not silently produce bogus signals. Accept either empty list or
        # a clean UnicodeDecodeError, but never a different crash.
        try:
            result = parse_cost_usage(path)
            assert isinstance(result, list)
        except UnicodeDecodeError:
            pass

    def test_unsupported_extension_returns_empty(self, tmp_path):
        path = _write(tmp_path, "data.xlsx", "not really xlsx")
        assert parse_cost_usage(path) == []

    def test_missing_file_raises_filenotfound(self):
        with pytest.raises(FileNotFoundError):
            parse_cost_usage("/nonexistent/path/to/file.csv")

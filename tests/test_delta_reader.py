"""Unit tests for forge/delta_engine/reader.py"""

import json
import logging
from pathlib import Path

import pytest

from forge.delta_engine.reader import read_history


@pytest.fixture
def sample_record() -> dict:
    """A valid JSONL record matching the expected format."""
    return {
        "timestamp": "2026-07-07T10:15:00Z",
        "forge_score": 62.4,
        "score_band": "GOVERNED",
        "pillar_scores": {
            "P1": 70.0,
            "P2": 55.0,
            "P3": 60.0,
            "P4": 65.0,
            "P5": 58.0,
            "P6": 50.0,
            "P7": 72.0,
            "P8": 48.0,
            "P9": 63.0,
        },
        "profile": {
            "architecture": "open_lakehouse",
            "workload": "rag_retrieval",
            "industry": "general",
            "agent_maturity": "pilot",
        },
    }


class TestReadHistoryMissingFile:
    """Tests for missing file handling."""

    def test_returns_empty_list_for_nonexistent_file(self, tmp_path):
        path = tmp_path / "does_not_exist.jsonl"
        result = read_history(path)
        assert result == []

    def test_accepts_string_path(self, tmp_path):
        path = str(tmp_path / "does_not_exist.jsonl")
        result = read_history(path)
        assert result == []


class TestReadHistoryEmptyFile:
    """Tests for empty file handling."""

    def test_returns_empty_list_for_empty_file(self, tmp_path):
        path = tmp_path / "empty.jsonl"
        path.write_text("")
        result = read_history(path)
        assert result == []

    def test_returns_empty_list_for_whitespace_only_file(self, tmp_path):
        path = tmp_path / "whitespace.jsonl"
        path.write_text("   \n  \n\n")
        result = read_history(path)
        assert result == []


class TestReadHistoryValidRecords:
    """Tests for valid JSONL parsing."""

    def test_single_record(self, tmp_path, sample_record):
        path = tmp_path / "history.jsonl"
        path.write_text(json.dumps(sample_record) + "\n")
        result = read_history(path)
        assert len(result) == 1
        assert result[0] == sample_record

    def test_multiple_records_preserved_in_order(self, tmp_path, sample_record):
        record2 = {**sample_record, "forge_score": 70.1, "timestamp": "2026-08-01T10:00:00Z"}
        path = tmp_path / "history.jsonl"
        lines = [json.dumps(sample_record), json.dumps(record2)]
        path.write_text("\n".join(lines) + "\n")
        result = read_history(path)
        assert len(result) == 2
        assert result[0]["forge_score"] == 62.4
        assert result[1]["forge_score"] == 70.1

    def test_returns_dicts(self, tmp_path, sample_record):
        path = tmp_path / "history.jsonl"
        path.write_text(json.dumps(sample_record) + "\n")
        result = read_history(path)
        assert isinstance(result[0], dict)

    def test_preserves_nested_structure(self, tmp_path, sample_record):
        path = tmp_path / "history.jsonl"
        path.write_text(json.dumps(sample_record) + "\n")
        result = read_history(path)
        assert result[0]["pillar_scores"]["P1"] == 70.0
        assert result[0]["profile"]["architecture"] == "open_lakehouse"


class TestReadHistoryMalformedLines:
    """Tests for malformed line handling."""

    def test_skips_malformed_line_returns_valid(self, tmp_path, sample_record):
        path = tmp_path / "history.jsonl"
        lines = [
            json.dumps(sample_record),
            "this is not valid json{{{",
            json.dumps({**sample_record, "forge_score": 75.0}),
        ]
        path.write_text("\n".join(lines) + "\n")
        result = read_history(path)
        assert len(result) == 2
        assert result[0]["forge_score"] == 62.4
        assert result[1]["forge_score"] == 75.0

    def test_logs_warning_for_malformed_line(self, tmp_path, caplog):
        path = tmp_path / "history.jsonl"
        path.write_text("not json at all\n")
        with caplog.at_level(logging.WARNING, logger="forge.delta_engine.reader"):
            result = read_history(path)
        assert result == []
        assert "Skipping malformed line 1" in caplog.text

    def test_all_malformed_returns_empty_list(self, tmp_path):
        path = tmp_path / "history.jsonl"
        path.write_text("bad1\nbad2\nbad3\n")
        result = read_history(path)
        assert result == []

    def test_handles_partial_json(self, tmp_path, sample_record):
        path = tmp_path / "history.jsonl"
        lines = [
            '{"incomplete": ',  # partial JSON
            json.dumps(sample_record),
        ]
        path.write_text("\n".join(lines) + "\n")
        result = read_history(path)
        assert len(result) == 1
        assert result[0] == sample_record

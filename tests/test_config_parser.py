"""Unit tests for forge.document_ingest.config_parser."""

import os
import tempfile

import pytest

from forge.document_ingest import DocumentEvidence
from forge.document_ingest.config_parser import parse_config_export


# --- Fixtures ---


@pytest.fixture
def txt_file_with_evidence(tmp_path):
    """Create a text file with multiple criterion-matching content."""
    content = (
        "Our Databricks workspace has Unity Catalog enabled.\n"
        "Lineage tracking is configured for all production pipelines.\n"
        "We use schema enforcement on all Delta Lake tables.\n"
        "System tables (audit logs) are active and queried weekly.\n"
    )
    file_path = tmp_path / "workspace_config.txt"
    file_path.write_text(content)
    return str(file_path)


@pytest.fixture
def empty_file(tmp_path):
    """Create an empty text file."""
    file_path = tmp_path / "empty.txt"
    file_path.write_text("")
    return str(file_path)


@pytest.fixture
def json_file(tmp_path):
    """Create a JSON file with config content."""
    content = '{"features": ["row filter enabled", "column masking configured"]}'
    file_path = tmp_path / "features.json"
    file_path.write_text(content)
    return str(file_path)


@pytest.fixture
def yaml_file(tmp_path):
    """Create a YAML file with config content."""
    content = (
        "services:\n"
        "  - name: auto loader\n"
        "    status: active\n"
        "  - name: structured streaming\n"
        "    status: active\n"
    )
    file_path = tmp_path / "services.yaml"
    file_path.write_text(content)
    return str(file_path)


@pytest.fixture
def no_match_file(tmp_path):
    """Create a text file with no matching patterns."""
    content = "This document discusses general cloud architecture best practices.\n"
    file_path = tmp_path / "general.txt"
    file_path.write_text(content)
    return str(file_path)


# --- Tests ---


class TestParseConfigExport:
    """Tests for the parse_config_export function."""

    def test_file_not_found_raises(self):
        """FileNotFoundError raised for nonexistent file."""
        with pytest.raises(FileNotFoundError):
            parse_config_export("/nonexistent/path/file.txt")

    def test_empty_file_returns_empty_list(self, empty_file):
        """Empty file returns empty evidence list."""
        result = parse_config_export(empty_file)
        assert result == []

    def test_no_match_returns_empty_list(self, no_match_file):
        """File with no matching patterns returns empty list."""
        result = parse_config_export(no_match_file)
        assert result == []

    def test_returns_document_evidence_objects(self, txt_file_with_evidence):
        """Results are DocumentEvidence instances."""
        result = parse_config_export(txt_file_with_evidence)
        assert len(result) > 0
        for item in result:
            assert isinstance(item, DocumentEvidence)

    def test_extracts_multiple_criteria(self, txt_file_with_evidence):
        """Multiple criteria extracted from a document with several mentions."""
        result = parse_config_export(txt_file_with_evidence)
        criterion_ids = {ev.criterion_id for ev in result}
        assert "P1.1" in criterion_ids  # Unity Catalog
        assert "P3.1" in criterion_ids  # Lineage tracking
        assert "P4.5" in criterion_ids  # Schema enforcement
        assert "P6.1" in criterion_ids  # System tables / audit

    def test_confidence_in_valid_range(self, txt_file_with_evidence):
        """All confidence scores are within 0.6–0.85."""
        result = parse_config_export(txt_file_with_evidence)
        for ev in result:
            assert 0.6 <= ev.confidence <= 0.85, (
                f"Confidence {ev.confidence} out of range for {ev.criterion_id}"
            )

    def test_score_is_populated(self, txt_file_with_evidence):
        """Score field is populated (1.0 for pattern matches)."""
        result = parse_config_export(txt_file_with_evidence)
        for ev in result:
            assert ev.score == 1.0

    def test_source_file_is_basename(self, txt_file_with_evidence):
        """Source file field contains just the filename, not full path."""
        result = parse_config_export(txt_file_with_evidence)
        for ev in result:
            assert ev.source_file == "workspace_config.txt"

    def test_evidence_contains_match(self, txt_file_with_evidence):
        """Evidence text is non-empty and descriptive."""
        result = parse_config_export(txt_file_with_evidence)
        for ev in result:
            assert len(ev.evidence) > 0
            assert ev.evidence != ""

    def test_json_file_parsing(self, json_file):
        """JSON files are parsed as text and evidence extracted."""
        result = parse_config_export(json_file)
        criterion_ids = {ev.criterion_id for ev in result}
        assert "P5.2" in criterion_ids  # row filter
        assert "P5.1" in criterion_ids  # column masking

    def test_yaml_file_parsing(self, yaml_file):
        """YAML files are parsed as text and evidence extracted."""
        result = parse_config_export(yaml_file)
        criterion_ids = {ev.criterion_id for ev in result}
        assert "P7.9" in criterion_ids  # auto loader
        assert "P7.1" in criterion_ids  # structured streaming

    def test_case_insensitive_matching(self, tmp_path):
        """Pattern matching is case-insensitive."""
        content = "UNITY CATALOG is our metadata layer. SCHEMA ENFORCEMENT is active."
        file_path = tmp_path / "upper.txt"
        file_path.write_text(content)
        result = parse_config_export(str(file_path))
        criterion_ids = {ev.criterion_id for ev in result}
        assert "P1.1" in criterion_ids
        assert "P4.5" in criterion_ids

    def test_one_evidence_per_criterion(self, tmp_path):
        """Only one evidence item produced per criterion (first match wins)."""
        # Content has multiple patterns that match P6.1
        content = (
            "We use system tables for compliance.\n"
            "Audit logs are reviewed quarterly.\n"
            "Audit is enabled for all workspaces.\n"
        )
        file_path = tmp_path / "multi.txt"
        file_path.write_text(content)
        result = parse_config_export(str(file_path))
        p6_1_items = [ev for ev in result if ev.criterion_id == "P6.1"]
        assert len(p6_1_items) == 1

    def test_whitespace_only_file(self, tmp_path):
        """File with only whitespace returns empty list."""
        file_path = tmp_path / "whitespace.txt"
        file_path.write_text("   \n\t\n   ")
        result = parse_config_export(str(file_path))
        assert result == []


class TestImportViaInit:
    """Test that parse_config_export is accessible via the __init__ re-export."""

    def test_import_from_package(self, txt_file_with_evidence):
        """parse_config_export is importable from forge.document_ingest."""
        from forge.document_ingest import parse_config_export as fn
        result = fn(txt_file_with_evidence)
        assert len(result) > 0

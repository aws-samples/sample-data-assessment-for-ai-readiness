"""Tests for _write_estate_roadmap_md in collector.py — multi-platform roadmap generation."""

import os
import tempfile
import pytest
from unittest.mock import patch
from datetime import datetime, timezone

from forge.models import (
    RelevanceStatus,
    CriterionType,
    ReadinessBand,
    CriterionSegmentResult,
    PlatformSegment,
    PillarScore,
    EstateAssessmentResult,
    AnalogDetail,
)
from forge.collector import _write_estate_roadmap_md


def _make_criterion_segment(
    pillar, index, name, score, platform,
    relevance=RelevanceStatus.RELEVANT,
    criterion_type=CriterionType.BINARY,
    evidence="Test evidence",
    analog_detail=None,
):
    """Helper to build a CriterionSegmentResult."""
    return CriterionSegmentResult(
        pillar=pillar,
        index=index,
        name=name,
        score=score,
        relevance_status=relevance,
        confidence_score=0.8,
        evidence=evidence,
        criterion_type=criterion_type,
        platform=platform,
        analog_detail=analog_detail,
    )


def _make_pillar_score(code, name, raw_score=50.0, criteria=None):
    """Helper to build a PillarScore."""
    return PillarScore(
        code=code,
        name=name,
        raw_score=raw_score,
        relevant_count=5,
        not_applicable_count=0,
        undetermined_count=0,
        criteria=criteria or [],
    )


def _make_segment(platform, forge_score, criteria, pillars=None):
    """Helper to build a PlatformSegment."""
    if pillars is None:
        # Derive pillar names from criteria
        pillar_codes = sorted(set(cr.pillar for cr in criteria))
        pillar_names = {
            "P1": "Agent Access & Discovery",
            "P3": "Data Lineage & Provenance",
            "P4": "Data Quality, Contracts & Classification",
            "P5": "Access Control, Identity & Tenancy",
            "P6": "Observability & Audit",
            "P7": "Real-Time, Freshness & Zero-ETL",
        }
        pillars = [
            _make_pillar_score(code, pillar_names.get(code, code))
            for code in pillar_codes
        ]

    return PlatformSegment(
        platform=platform,
        source_type="api_discovery" if platform == "aws" else "conversational",
        pillars=pillars,
        criteria=criteria,
        summary={"forge_score": forge_score, "readiness_band": "GOVERNED"},
        metadata={},
    )


def _make_estate_result(segments, estate_score=59.8, estate_band=ReadinessBand.GOVERNED):
    """Helper to build an EstateAssessmentResult."""
    all_criteria = []
    for seg in segments:
        all_criteria.extend(seg.criteria)

    merged_pillars = [
        _make_pillar_score("P1", "Agent Access & Discovery"),
        _make_pillar_score("P4", "Data Quality, Contracts & Classification"),
    ]

    return EstateAssessmentResult(
        segments=segments,
        merged_pillars=merged_pillars,
        merged_criteria=all_criteria,
        estate_score=estate_score,
        estate_band=estate_band,
        estate_raw_score=64.5,
        estate_coverage_multiplier=0.927,
        metadata={
            "customer_name": "Test Corp",
            "timestamp": "2026-07-20T14:30:00+00:00",
            "platforms_assessed": [s.platform for s in segments],
        },
    )


class TestEstateRoadmapMdHeader:
    """Header shows estate score, band, and per-platform scores."""

    def test_header_contains_estate_score_and_band(self, tmp_path):
        aws_criteria = [
            _make_criterion_segment("P1", 1, "Catalog coverage", 0.3, "aws"),
        ]
        segments = [_make_segment("aws", 68.5, aws_criteria)]
        result = _make_estate_result(segments, estate_score=68.5, estate_band=ReadinessBand.GOVERNED)

        with patch("forge.collector.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 7, 20, 14, 30, 0, tzinfo=timezone.utc)
            mock_dt.side_effect = lambda *a, **k: datetime(*a, **k)
            os.chdir(tmp_path)
            _write_estate_roadmap_md(result, {"P1": 18.5})

        # Find the written file
        roadmap_dir = tmp_path / "forge_output" / "roadmaps"
        files = list(roadmap_dir.glob("forge_estate_roadmap_*.md"))
        assert len(files) == 1

        content = files[0].read_text()
        assert "# FORGE Estate Remediation Roadmap" in content
        assert "**Estate Score:** 68.5 (GOVERNED)" in content

    def test_header_shows_per_platform_scores(self, tmp_path):
        aws_criteria = [
            _make_criterion_segment("P1", 1, "API Access", 0.3, "aws"),
        ]
        dbx_criteria = [
            _make_criterion_segment("P4", 2, "Tables with DQ rules", 0.2, "databricks"),
        ]
        segments = [
            _make_segment("aws", 68.5, aws_criteria),
            _make_segment("databricks", 47.2, dbx_criteria),
        ]
        result = _make_estate_result(segments, estate_score=59.8)

        os.chdir(tmp_path)
        _write_estate_roadmap_md(result, {"P1": 18.5, "P4": 15.0})

        roadmap_dir = tmp_path / "forge_output" / "roadmaps"
        files = list(roadmap_dir.glob("forge_estate_roadmap_*.md"))
        content = files[0].read_text()

        assert "AWS (68.5)" in content
        assert "DATABRICKS (47.2)" in content


class TestPlatformGrouping:
    """Remediation sections are split by platform."""

    def test_remediation_grouped_by_platform(self, tmp_path):
        aws_criteria = [
            _make_criterion_segment("P1", 6, "Catalog covers >80%", 0.4, "aws"),
        ]
        dbx_criteria = [
            _make_criterion_segment("P4", 2, "Tables with DQ rules", 0.2, "databricks"),
        ]
        segments = [
            _make_segment("aws", 68.5, aws_criteria),
            _make_segment("databricks", 47.2, dbx_criteria),
        ]
        result = _make_estate_result(segments)

        os.chdir(tmp_path)
        _write_estate_roadmap_md(result, {"P1": 18.5, "P4": 15.0})

        roadmap_dir = tmp_path / "forge_output" / "roadmaps"
        files = list(roadmap_dir.glob("forge_estate_roadmap_*.md"))
        content = files[0].read_text()

        assert "## AWS Remediation" in content
        assert "## DATABRICKS Remediation" in content

    def test_criteria_sorted_by_pillar_then_index(self, tmp_path):
        dbx_criteria = [
            _make_criterion_segment("P4", 5, "Schema enforcement", 0.1, "databricks"),
            _make_criterion_segment("P1", 3, "Schema introspection", 0.0, "databricks"),
            _make_criterion_segment("P4", 2, "Tables with DQ", 0.2, "databricks"),
            _make_criterion_segment("P1", 1, "UC API queryable", 0.0, "databricks"),
        ]
        segments = [_make_segment("databricks", 47.2, dbx_criteria)]
        result = _make_estate_result(segments)

        os.chdir(tmp_path)
        _write_estate_roadmap_md(result, {"P1": 18.5, "P4": 15.0})

        roadmap_dir = tmp_path / "forge_output" / "roadmaps"
        files = list(roadmap_dir.glob("forge_estate_roadmap_*.md"))
        content = files[0].read_text()

        # P1 criteria should come before P4 criteria
        p1_pos = content.index("P1.1")
        p4_pos = content.index("P4.2")
        assert p1_pos < p4_pos

        # Within P1, index 1 before index 3
        p1_1_pos = content.index("P1.1")
        p1_3_pos = content.index("P1.3")
        assert p1_1_pos < p1_3_pos


class TestCriterionFiltering:
    """Only score < 0.5 and RELEVANT criteria appear."""

    def test_met_criteria_excluded(self, tmp_path):
        aws_criteria = [
            _make_criterion_segment("P1", 1, "Met criterion", 0.9, "aws"),
            _make_criterion_segment("P1", 2, "Unmet criterion", 0.3, "aws"),
        ]
        segments = [_make_segment("aws", 68.5, aws_criteria)]
        result = _make_estate_result(segments)

        os.chdir(tmp_path)
        _write_estate_roadmap_md(result, {"P1": 18.5})

        roadmap_dir = tmp_path / "forge_output" / "roadmaps"
        files = list(roadmap_dir.glob("forge_estate_roadmap_*.md"))
        content = files[0].read_text()

        assert "Met criterion" not in content
        assert "Unmet criterion" in content

    def test_not_applicable_excluded(self, tmp_path):
        aws_criteria = [
            _make_criterion_segment("P1", 1, "N/A criterion", 0.0, "aws",
                                    relevance=RelevanceStatus.NOT_APPLICABLE),
            _make_criterion_segment("P1", 2, "Relevant unmet", 0.3, "aws"),
        ]
        segments = [_make_segment("aws", 68.5, aws_criteria)]
        result = _make_estate_result(segments)

        os.chdir(tmp_path)
        _write_estate_roadmap_md(result, {"P1": 18.5})

        roadmap_dir = tmp_path / "forge_output" / "roadmaps"
        files = list(roadmap_dir.glob("forge_estate_roadmap_*.md"))
        content = files[0].read_text()

        assert "N/A criterion" not in content
        assert "Relevant unmet" in content


class TestDatabricksServiceReferences:
    """Databricks criteria include service references from registry."""

    def test_databricks_criteria_show_service_names(self, tmp_path):
        dbx_criteria = [
            _make_criterion_segment("P4", 2, "Tables with DQ rules", 0.2, "databricks"),
        ]
        segments = [_make_segment("databricks", 47.2, dbx_criteria)]
        result = _make_estate_result(segments)

        os.chdir(tmp_path)
        _write_estate_roadmap_md(result, {"P4": 15.0})

        roadmap_dir = tmp_path / "forge_output" / "roadmaps"
        files = list(roadmap_dir.glob("forge_estate_roadmap_*.md"))
        content = files[0].read_text()

        # P4.2 maps to delta_live_tables → "Delta Live Tables"
        assert "Delta Live Tables" in content

    def test_aws_criteria_do_not_have_databricks_services(self, tmp_path):
        aws_criteria = [
            _make_criterion_segment("P1", 1, "Catalog coverage", 0.3, "aws"),
        ]
        segments = [_make_segment("aws", 68.5, aws_criteria)]
        result = _make_estate_result(segments)

        os.chdir(tmp_path)
        _write_estate_roadmap_md(result, {"P1": 18.5})

        roadmap_dir = tmp_path / "forge_output" / "roadmaps"
        files = list(roadmap_dir.glob("forge_estate_roadmap_*.md"))
        content = files[0].read_text()

        # No Databricks service references for AWS criteria
        assert "Unity Catalog" not in content
        assert "Delta Live Tables" not in content


class TestEvidenceDisplay:
    """Each criterion shows its evidence text."""

    def test_evidence_shown_in_roadmap(self, tmp_path):
        aws_criteria = [
            _make_criterion_segment("P1", 1, "Catalog coverage", 0.3, "aws",
                                    evidence="Only 30% of tables cataloged"),
        ]
        segments = [_make_segment("aws", 68.5, aws_criteria)]
        result = _make_estate_result(segments)

        os.chdir(tmp_path)
        _write_estate_roadmap_md(result, {"P1": 18.5})

        roadmap_dir = tmp_path / "forge_output" / "roadmaps"
        files = list(roadmap_dir.glob("forge_estate_roadmap_*.md"))
        content = files[0].read_text()

        assert "Evidence: Only 30% of tables cataloged" in content

    def test_no_evidence_placeholder_excluded(self, tmp_path):
        aws_criteria = [
            _make_criterion_segment("P1", 1, "Catalog coverage", 0.3, "aws",
                                    evidence="No evidence"),
        ]
        segments = [_make_segment("aws", 68.5, aws_criteria)]
        result = _make_estate_result(segments)

        os.chdir(tmp_path)
        _write_estate_roadmap_md(result, {"P1": 18.5})

        roadmap_dir = tmp_path / "forge_output" / "roadmaps"
        files = list(roadmap_dir.glob("forge_estate_roadmap_*.md"))
        content = files[0].read_text()

        assert "Evidence: No evidence" not in content


class TestNoGapsPlatform:
    """When a platform has no gaps, display a message."""

    def test_no_gaps_message(self, tmp_path):
        aws_criteria = [
            _make_criterion_segment("P1", 1, "All good", 0.9, "aws"),
        ]
        segments = [_make_segment("aws", 90.0, aws_criteria)]
        result = _make_estate_result(segments, estate_score=90.0, estate_band=ReadinessBand.AGENT_READY)

        os.chdir(tmp_path)
        _write_estate_roadmap_md(result, {"P1": 18.5})

        roadmap_dir = tmp_path / "forge_output" / "roadmaps"
        files = list(roadmap_dir.glob("forge_estate_roadmap_*.md"))
        content = files[0].read_text()

        assert "No unmet criteria" in content

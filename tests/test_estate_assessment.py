"""
Unit tests for run_estate_assessment in forge/collector.py.

Tests that the collector correctly merges platform segments into an
EstateAssessmentResult and writes the estate JSON artifact.

Validates: Requirements 8.1
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from forge.models import (
    AnalogDetail,
    CriterionSegmentResult,
    CriterionType,
    EstateAssessmentResult,
    PillarScore,
    PlatformSegment,
    ReadinessBand,
    RelevanceStatus,
)
from forge.collector import run_estate_assessment, _write_estate_json, _append_estate_history_record


# ─── Fixtures ──────────────────────────────────────────────────────────────────


def _make_criterion(pillar: str, index: int, score: float, platform: str,
                    criterion_type=CriterionType.BINARY,
                    relevance=RelevanceStatus.RELEVANT,
                    analog_detail=None) -> CriterionSegmentResult:
    """Helper to create a CriterionSegmentResult."""
    return CriterionSegmentResult(
        pillar=pillar,
        index=index,
        name=f"Test {pillar}.{index}",
        score=score,
        relevance_status=relevance,
        confidence_score=0.85,
        evidence="Test evidence",
        criterion_type=criterion_type,
        platform=platform,
        analog_detail=analog_detail,
        exclusion_reason=None,
    )


def _make_segment(platform: str, criteria: list[CriterionSegmentResult]) -> PlatformSegment:
    """Helper to create a PlatformSegment with minimal data."""
    # Build pillar scores from criteria
    from collections import defaultdict
    pillar_criteria = defaultdict(list)
    for cr in criteria:
        pillar_criteria[cr.pillar].append(cr)

    pillars = []
    for code in sorted(pillar_criteria.keys()):
        crs = pillar_criteria[code]
        relevant = [c for c in crs if c.relevance_status == RelevanceStatus.RELEVANT]
        raw_score = 0.0
        if relevant:
            raw_score = round((sum(c.score for c in relevant) / len(relevant)) * 100, 2)
        pillars.append(PillarScore(
            code=code,
            name=f"Pillar {code}",
            raw_score=raw_score,
            relevant_count=len(relevant),
            not_applicable_count=0,
            undetermined_count=0,
            criteria=[],
        ))

    return PlatformSegment(
        platform=platform,
        source_type="api_discovery" if platform == "aws" else "conversational",
        pillars=pillars,
        criteria=criteria,
        summary={"forge_score": 60.0, "readiness_band": "GOVERNED"},
        metadata={"platform": platform},
    )


# ─── Tests ─────────────────────────────────────────────────────────────────────


class TestRunEstateAssessment:
    """Tests for run_estate_assessment function."""

    def test_empty_segments_raises_value_error(self, tmp_path):
        """run_estate_assessment raises ValueError for empty segments list."""
        with pytest.raises(ValueError, match="At least one platform segment"):
            run_estate_assessment(segments=[], profile_path=tmp_path / "fake.yaml")

    def test_single_segment_returns_estate_result(self, tmp_path):
        """Single-platform assessment produces a valid EstateAssessmentResult."""
        # Create a minimal profile file
        profile_path = _create_test_profile(tmp_path)

        # Create a single AWS segment with criteria for P1
        criteria = [
            _make_criterion("P1", 1, 1.0, "aws"),
            _make_criterion("P1", 2, 0.0, "aws"),
            _make_criterion("P2", 1, 1.0, "aws"),
        ]
        segment = _make_segment("aws", criteria)

        result = run_estate_assessment(
            segments=[segment],
            profile_path=profile_path,
            customer_name="Test Corp",
        )

        assert isinstance(result, EstateAssessmentResult)
        assert result.estate_score >= 0.0
        assert result.estate_score <= 100.0
        assert result.estate_band in ReadinessBand
        assert len(result.segments) == 1
        assert result.metadata["customer_name"] == "Test Corp"
        assert result.metadata["platforms_assessed"] == ["aws"]

    def test_two_segments_merges_correctly(self, tmp_path):
        """Two platform segments are merged into an estate result."""
        profile_path = _create_test_profile(tmp_path)

        aws_criteria = [
            _make_criterion("P1", 1, 1.0, "aws"),
            _make_criterion("P1", 2, 0.8, "aws", CriterionType.ANALOG,
                           analog_detail=AnalogDetail(numerator=80, denominator=100, platform="aws")),
        ]
        dbx_criteria = [
            _make_criterion("P1", 1, 1.0, "databricks"),
            _make_criterion("P1", 2, 0.6, "databricks", CriterionType.ANALOG,
                           analog_detail=AnalogDetail(numerator=30, denominator=50, platform="databricks")),
        ]

        aws_segment = _make_segment("aws", aws_criteria)
        dbx_segment = _make_segment("databricks", dbx_criteria)

        result = run_estate_assessment(
            segments=[aws_segment, dbx_segment],
            profile_path=profile_path,
            customer_name="Multi Corp",
        )

        assert isinstance(result, EstateAssessmentResult)
        assert len(result.segments) == 2
        assert result.metadata["platforms_assessed"] == ["aws", "databricks"]
        # Merged criteria should have platform="estate"
        for cr in result.merged_criteria:
            assert cr.platform == "estate"
        # Estate score should be in valid range
        assert 0.0 <= result.estate_score <= 100.0

    def test_metadata_includes_required_fields(self, tmp_path):
        """Metadata contains customer_name, timestamp, collector_version, platforms_assessed."""
        profile_path = _create_test_profile(tmp_path)

        criteria = [_make_criterion("P1", 1, 1.0, "aws")]
        segment = _make_segment("aws", criteria)

        result = run_estate_assessment(
            segments=[segment],
            profile_path=profile_path,
            customer_name="Meta Test",
        )

        assert "customer_name" in result.metadata
        assert "timestamp" in result.metadata
        assert "collector_version" in result.metadata
        assert "platforms_assessed" in result.metadata


class TestWriteEstateJson:
    """Tests for _write_estate_json output format."""

    def test_writes_valid_json(self, tmp_path):
        """_write_estate_json produces valid JSON with the expected structure."""
        # Create a minimal EstateAssessmentResult
        criteria = [
            _make_criterion("P1", 1, 1.0, "estate"),
        ]
        pillars = [PillarScore(
            code="P1", name="Agent Access", raw_score=100.0,
            relevant_count=1, not_applicable_count=0, undetermined_count=0,
            criteria=[],
        )]

        segment = _make_segment("aws", [_make_criterion("P1", 1, 1.0, "aws")])

        result = EstateAssessmentResult(
            segments=[segment],
            merged_pillars=pillars,
            merged_criteria=criteria,
            estate_score=72.5,
            estate_band=ReadinessBand.GOVERNED,
            estate_raw_score=75.0,
            estate_coverage_multiplier=0.967,
            metadata={
                "customer_name": "JSON Test",
                "timestamp": "2026-01-01T00:00:00Z",
                "collector_version": "2.3.0",
                "platforms_assessed": ["aws"],
            },
        )

        weights = {"P1": 18.5, "P2": 12.0}
        floors = {"P1": 35, "P2": 30}

        # Write to a temporary directory
        original_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            _write_estate_json(result, weights, floors)

            # Find the written file
            assessments_dir = tmp_path / "forge_output" / "assessments"
            json_files = list(assessments_dir.glob("forge_estate_assessment_*.json"))
            assert len(json_files) == 1

            with open(json_files[0]) as f:
                data = json.load(f)

            # Verify top-level structure
            assert "metadata" in data
            assert "effective_weights" in data
            assert "effective_floors" in data
            assert "estate" in data
            assert "segments" in data
            assert "merged_pillars" in data
            assert "merged_criteria" in data

            # Verify estate section
            assert data["estate"]["forge_score"] == 72.5
            assert data["estate"]["score_band"] == "GOVERNED"
            assert data["estate"]["raw_score"] == 75.0
            assert data["estate"]["coverage_multiplier"] == 0.967

            # Verify segments contain expected fields
            assert len(data["segments"]) == 1
            seg = data["segments"][0]
            assert seg["platform"] == "aws"
            assert seg["source_type"] == "api_discovery"
        finally:
            os.chdir(original_cwd)


# ─── Helpers ───────────────────────────────────────────────────────────────────


def _create_test_profile(tmp_path: Path) -> Path:
    """Create a minimal forge_profile.yaml for testing."""
    profile_content = """profile:
  architecture: hybrid
  workload: multi_tool_agents
  industry: financial_services
  agent_maturity: single_agent_prod
locked: true
"""
    profile_path = tmp_path / "forge_profile.yaml"
    profile_path.write_text(profile_content)
    return profile_path


class TestAppendEstateHistoryRecord:
    """Tests for _append_estate_history_record function.

    Validates: Requirements 8.2
    """

    def _make_profile(self, tmp_path: Path):
        """Create and load a ForgeProfile for testing."""
        from forge.profile_engine import load_profile
        profile_path = _create_test_profile(tmp_path)
        return load_profile(profile_path)

    def _make_estate_result(self, segments: list[PlatformSegment]) -> EstateAssessmentResult:
        """Create a minimal EstateAssessmentResult for testing."""
        pillars = [PillarScore(
            code="P1", name="Agent Access", raw_score=65.0,
            relevant_count=2, not_applicable_count=0, undetermined_count=0,
            criteria=[],
        )]
        criteria = [_make_criterion("P1", 1, 1.0, "estate")]

        return EstateAssessmentResult(
            segments=segments,
            merged_pillars=pillars,
            merged_criteria=criteria,
            estate_score=59.8,
            estate_band=ReadinessBand.GOVERNED,
            estate_raw_score=64.5,
            estate_coverage_multiplier=0.927,
            metadata={
                "customer_name": "Test Corp",
                "timestamp": "2026-07-20T14:30:00Z",
                "collector_version": "2.3.0",
                "platforms_assessed": [s.platform for s in segments],
            },
        )

    def test_single_platform_backward_compat_format(self, tmp_path):
        """Single segment produces backward-compatible format without platform_scores."""
        profile = self._make_profile(tmp_path)

        criteria = [_make_criterion("P1", 1, 1.0, "aws")]
        segment = _make_segment("aws", criteria)
        result = self._make_estate_result([segment])

        original_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            _append_estate_history_record(result, profile)

            history_file = tmp_path / "forge_output" / "forge_history.jsonl"
            assert history_file.exists()

            with open(history_file) as f:
                record = json.loads(f.readline())

            # Should use forge_score/score_band keys
            assert "forge_score" in record
            assert "score_band" in record
            assert record["forge_score"] == 59.8
            assert record["score_band"] == "GOVERNED"

            # Should NOT include multi-platform fields
            assert "estate_score" not in record
            assert "estate_band" not in record
            assert "platform_scores" not in record
            assert "platforms_assessed" not in record

            # Should include standard fields
            assert "timestamp" in record
            assert "pillar_scores" in record
            assert "profile" in record
            assert record["pillar_scores"]["P1"] == 65.0
        finally:
            os.chdir(original_cwd)

    def test_multi_platform_includes_estate_and_platform_scores(self, tmp_path):
        """Multiple segments produce multi-platform format with estate_score and platform_scores."""
        profile = self._make_profile(tmp_path)

        aws_criteria = [_make_criterion("P1", 1, 1.0, "aws")]
        dbx_criteria = [_make_criterion("P1", 1, 0.0, "databricks")]
        aws_segment = _make_segment("aws", aws_criteria)
        dbx_segment = _make_segment("databricks", dbx_criteria)
        # Override the summary forge_scores to test platform_scores extraction
        aws_segment.summary["forge_score"] = 68.5
        dbx_segment.summary["forge_score"] = 47.2

        result = self._make_estate_result([aws_segment, dbx_segment])

        original_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            _append_estate_history_record(result, profile)

            history_file = tmp_path / "forge_output" / "forge_history.jsonl"
            assert history_file.exists()

            with open(history_file) as f:
                record = json.loads(f.readline())

            # Should include estate-level fields
            assert record["estate_score"] == 59.8
            assert record["estate_band"] == "GOVERNED"

            # Should include backward compat aliases
            assert record["forge_score"] == 59.8
            assert record["score_band"] == "GOVERNED"

            # Should include per-platform scores
            assert record["platform_scores"] == {"aws": 68.5, "databricks": 47.2}

            # Should include platforms_assessed
            assert record["platforms_assessed"] == ["aws", "databricks"]

            # Should include standard fields
            assert "timestamp" in record
            assert "pillar_scores" in record
            assert "profile" in record
        finally:
            os.chdir(original_cwd)

    def test_history_record_appends_not_overwrites(self, tmp_path):
        """Multiple calls append separate lines to forge_history.jsonl."""
        profile = self._make_profile(tmp_path)

        criteria = [_make_criterion("P1", 1, 1.0, "aws")]
        segment = _make_segment("aws", criteria)
        result = self._make_estate_result([segment])

        original_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            _append_estate_history_record(result, profile)
            _append_estate_history_record(result, profile)

            history_file = tmp_path / "forge_output" / "forge_history.jsonl"
            lines = history_file.read_text().strip().split("\n")
            assert len(lines) == 2

            # Both should be valid JSON
            for line in lines:
                record = json.loads(line)
                assert "forge_score" in record
        finally:
            os.chdir(original_cwd)

    def test_profile_dict_is_included(self, tmp_path):
        """The profile section includes architecture, workload, industry, agent_maturity."""
        profile = self._make_profile(tmp_path)

        criteria = [_make_criterion("P1", 1, 1.0, "aws")]
        segment = _make_segment("aws", criteria)
        result = self._make_estate_result([segment])

        original_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            _append_estate_history_record(result, profile)

            history_file = tmp_path / "forge_output" / "forge_history.jsonl"
            with open(history_file) as f:
                record = json.loads(f.readline())

            assert record["profile"]["architecture"] == "hybrid"
            assert record["profile"]["workload"] == "multi_tool_agents"
            assert record["profile"]["industry"] == "financial_services"
            assert record["profile"]["agent_maturity"] == "single_agent_prod"
        finally:
            os.chdir(original_cwd)

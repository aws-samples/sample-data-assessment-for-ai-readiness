"""Tests for _generate_estate_criteria_html — criteria drill-down with platform badges."""

import pytest

from forge.dashboard.generator import (
    _generate_estate_criteria_html,
    _build_analog_evidence,
    _build_binary_failure_evidence,
)


# ─── Fixtures ─────────────────────────────────────────────────────────────────

def _make_segment(platform, criteria):
    """Helper to build a minimal platform segment dict."""
    return {
        "platform": platform,
        "forge_score": 60.0,
        "score_band": "GOVERNED",
        "pillars": [],
        "criteria": criteria,
    }


def _make_criterion(pillar, index, name, score, criterion_type="BINARY",
                    platform="estate", evidence="N/A", confidence_score=0.75,
                    relevance_status="RELEVANT", analog_detail=None):
    """Helper to build a criterion dict."""
    c = {
        "pillar": pillar,
        "index": index,
        "name": name,
        "score": score,
        "criterion_type": criterion_type,
        "platform": platform,
        "evidence": evidence,
        "confidence_score": confidence_score,
        "relevance_status": relevance_status,
    }
    if analog_detail:
        c["analog_detail"] = analog_detail
    return c


# ─── Platform Badge Tests ─────────────────────────────────────────────────────

class TestPlatformBadgeColumn:
    """Criteria table should show platform badges for each criterion."""

    def test_platform_column_header_present(self):
        merged = [_make_criterion("P1", 1, "UC API queryable", 1.0)]
        segments = [_make_segment("aws", [
            _make_criterion("P1", 1, "UC API queryable", 1.0, platform="aws")
        ])]
        result = _generate_estate_criteria_html(merged, segments)
        assert "<th>Platform</th>" in result

    def test_single_platform_aws_badge(self):
        merged = [_make_criterion("P1", 1, "Glue Catalog API", 1.0)]
        segments = [
            _make_segment("aws", [
                _make_criterion("P1", 1, "Glue Catalog API", 1.0, platform="aws")
            ]),
            _make_segment("databricks", [
                _make_criterion("P1", 1, "Glue Catalog API", 0.0,
                                platform="databricks", relevance_status="NOT_APPLICABLE")
            ]),
        ]
        result = _generate_estate_criteria_html(merged, segments)
        assert 'class="platform-tag aws"' in result
        assert ">AWS<" in result

    def test_single_platform_dbx_badge(self):
        merged = [_make_criterion("P1", 1, "Unity Catalog API", 1.0)]
        segments = [
            _make_segment("aws", [
                _make_criterion("P1", 1, "Unity Catalog API", 0.0,
                                platform="aws", relevance_status="NOT_APPLICABLE")
            ]),
            _make_segment("databricks", [
                _make_criterion("P1", 1, "Unity Catalog API", 1.0, platform="databricks")
            ]),
        ]
        result = _generate_estate_criteria_html(merged, segments)
        assert 'class="platform-tag dbx"' in result
        assert ">DBX<" in result

    def test_both_platforms_badge(self):
        merged = [_make_criterion("P4", 2, "Tables with DQ rules", 0.667,
                                  criterion_type="ANALOG")]
        segments = [
            _make_segment("aws", [
                _make_criterion("P4", 2, "Tables with DQ rules", 0.8,
                                criterion_type="ANALOG", platform="aws",
                                analog_detail={"numerator": 80, "denominator": 100})
            ]),
            _make_segment("databricks", [
                _make_criterion("P4", 2, "Tables with DQ rules", 0.4,
                                criterion_type="ANALOG", platform="databricks",
                                analog_detail={"numerator": 20, "denominator": 50})
            ]),
        ]
        result = _generate_estate_criteria_html(merged, segments)
        # Both platform badges shown
        assert 'class="platform-tag aws"' in result
        assert 'class="platform-tag dbx"' in result


# ─── Binary Failure Evidence Tests ────────────────────────────────────────────

class TestBinaryFailureEvidence:
    """Binary criteria that failed should show which platform(s) failed."""

    def test_binary_failed_on_one_platform(self):
        merged = [_make_criterion("P5", 1, "Column masking", 0.0)]
        segments = [
            _make_segment("aws", [
                _make_criterion("P5", 1, "Column masking", 1.0, platform="aws")
            ]),
            _make_segment("databricks", [
                _make_criterion("P5", 1, "Column masking", 0.0, platform="databricks")
            ]),
        ]
        result = _generate_estate_criteria_html(merged, segments)
        assert "Failed on: databricks" in result

    def test_binary_failed_on_both_platforms(self):
        merged = [_make_criterion("P6", 1, "Audit logs enabled", 0.0)]
        segments = [
            _make_segment("aws", [
                _make_criterion("P6", 1, "Audit logs enabled", 0.0, platform="aws")
            ]),
            _make_segment("databricks", [
                _make_criterion("P6", 1, "Audit logs enabled", 0.0, platform="databricks")
            ]),
        ]
        result = _generate_estate_criteria_html(merged, segments)
        assert "Failed on:" in result
        assert "aws" in result
        assert "databricks" in result

    def test_binary_passing_no_failure_evidence(self):
        merged = [_make_criterion("P1", 1, "API queryable", 1.0)]
        segments = [
            _make_segment("aws", [
                _make_criterion("P1", 1, "API queryable", 1.0, platform="aws")
            ]),
            _make_segment("databricks", [
                _make_criterion("P1", 1, "API queryable", 1.0, platform="databricks")
            ]),
        ]
        result = _generate_estate_criteria_html(merged, segments)
        assert "Failed on:" not in result


# ─── Analog Evidence Tests ────────────────────────────────────────────────────

class TestAnalogEvidence:
    """Analog criteria should show per-platform breakdown."""

    def test_analog_shows_combined_and_breakdown(self):
        merged = [_make_criterion("P4", 2, "Tables with DQ rules", 0.667,
                                  criterion_type="ANALOG")]
        segments = [
            _make_segment("aws", [
                _make_criterion("P4", 2, "Tables with DQ rules", 0.8,
                                criterion_type="ANALOG", platform="aws",
                                analog_detail={"numerator": 80, "denominator": 100})
            ]),
            _make_segment("databricks", [
                _make_criterion("P4", 2, "Tables with DQ rules", 0.4,
                                criterion_type="ANALOG", platform="databricks",
                                analog_detail={"numerator": 20, "denominator": 50})
            ]),
        ]
        result = _generate_estate_criteria_html(merged, segments)
        assert "Combined: 66.7%" in result
        assert "AWS: 80/100" in result
        assert "DBX: 20/50" in result

    def test_analog_single_platform(self):
        merged = [_make_criterion("P4", 2, "Tables with DQ rules", 0.8,
                                  criterion_type="ANALOG")]
        segments = [
            _make_segment("aws", [
                _make_criterion("P4", 2, "Tables with DQ rules", 0.8,
                                criterion_type="ANALOG", platform="aws",
                                analog_detail={"numerator": 80, "denominator": 100})
            ]),
            _make_segment("databricks", [
                _make_criterion("P4", 2, "Tables with DQ rules", 0.0,
                                criterion_type="ANALOG", platform="databricks",
                                relevance_status="NOT_APPLICABLE")
            ]),
        ]
        result = _generate_estate_criteria_html(merged, segments)
        assert "Combined: 80.0%" in result
        assert "AWS: 80/100" in result


# ─── Helper Function Unit Tests ───────────────────────────────────────────────

class TestBuildAnalogEvidence:
    """Unit tests for _build_analog_evidence helper."""

    def test_two_platforms(self):
        merged = {"score": 0.667, "evidence": "Pooled"}
        per_platform = [
            {"platform": "aws", "score": 0.8, "relevance_status": "RELEVANT",
             "analog_detail": {"numerator": 80, "denominator": 100}},
            {"platform": "databricks", "score": 0.4, "relevance_status": "RELEVANT",
             "analog_detail": {"numerator": 20, "denominator": 50}},
        ]
        labels = {"aws": "AWS", "databricks": "DBX"}
        result = _build_analog_evidence(merged, per_platform, labels)
        assert "Combined: 66.7%" in result
        assert "AWS: 80/100" in result
        assert "DBX: 20/50" in result

    def test_no_analog_detail_fallback(self):
        merged = {"score": 0.5, "evidence": "Pooled"}
        per_platform = [
            {"platform": "aws", "score": 0.5, "relevance_status": "RELEVANT"},
        ]
        labels = {"aws": "AWS", "databricks": "DBX"}
        result = _build_analog_evidence(merged, per_platform, labels)
        assert "Combined: 50.0%" in result
        assert "AWS: 50%" in result

    def test_empty_per_platform_uses_merged_evidence(self):
        merged = {"score": 0.75, "evidence": "Custom evidence text"}
        per_platform = []
        labels = {"aws": "AWS", "databricks": "DBX"}
        result = _build_analog_evidence(merged, per_platform, labels)
        assert result == "Custom evidence text"


class TestBuildBinaryFailureEvidence:
    """Unit tests for _build_binary_failure_evidence helper."""

    def test_one_platform_failed(self):
        merged = {"score": 0.0, "evidence": "Failed"}
        per_platform = [
            {"platform": "aws", "score": 1.0, "relevance_status": "RELEVANT"},
            {"platform": "databricks", "score": 0.0, "relevance_status": "RELEVANT"},
        ]
        labels = {"aws": "AWS", "databricks": "DBX"}
        result = _build_binary_failure_evidence(merged, per_platform, labels)
        assert result == "Failed on: databricks"

    def test_both_platforms_failed(self):
        merged = {"score": 0.0, "evidence": "Failed"}
        per_platform = [
            {"platform": "aws", "score": 0.0, "relevance_status": "RELEVANT"},
            {"platform": "databricks", "score": 0.0, "relevance_status": "RELEVANT"},
        ]
        labels = {"aws": "AWS", "databricks": "DBX"}
        result = _build_binary_failure_evidence(merged, per_platform, labels)
        assert "aws" in result
        assert "databricks" in result

    def test_not_applicable_excluded(self):
        merged = {"score": 0.0, "evidence": "Failed"}
        per_platform = [
            {"platform": "aws", "score": 0.0, "relevance_status": "RELEVANT"},
            {"platform": "databricks", "score": 0.0, "relevance_status": "NOT_APPLICABLE"},
        ]
        labels = {"aws": "AWS", "databricks": "DBX"}
        result = _build_binary_failure_evidence(merged, per_platform, labels)
        assert result == "Failed on: aws"

"""Unit tests for forge.platform_segments.aws_adapter."""

import pytest

from forge.models import (
    AnalogDetail,
    CriterionResult,
    CriterionSegmentResult,
    CriterionType,
    ForgeAssessmentResult,
    PillarScore,
    PlatformSegment,
    RelevanceStatus,
)
from forge.platform_segments.aws_adapter import wrap_aws_result


# --- Fixtures ---


@pytest.fixture
def binary_criterion() -> CriterionResult:
    """A simple binary criterion that passed."""
    return CriterionResult(
        pillar="P1",
        index=1,
        name="API queryable",
        score=1.0,
        relevance_status=RelevanceStatus.RELEVANT,
        confidence_score=0.95,
        evidence="GetDatabases API succeeded",
        criterion_type=CriterionType.BINARY,
    )


@pytest.fixture
def binary_criterion_failed() -> CriterionResult:
    """A binary criterion that failed."""
    return CriterionResult(
        pillar="P1",
        index=2,
        name="Catalog REST API",
        score=0.0,
        relevance_status=RelevanceStatus.RELEVANT,
        confidence_score=0.70,
        evidence="No Iceberg REST stacks found",
        criterion_type=CriterionType.BINARY,
    )


@pytest.fixture
def analog_criterion() -> CriterionResult:
    """An analog criterion with partial coverage."""
    return CriterionResult(
        pillar="P1",
        index=6,
        name="Catalog covers >80%",
        score=0.75,
        relevance_status=RelevanceStatus.RELEVANT,
        confidence_score=0.60,
        evidence="Found 75 of 100 tables in Glue catalog",
        criterion_type=CriterionType.ANALOG,
    )


@pytest.fixture
def not_applicable_criterion() -> CriterionResult:
    """A criterion that is not applicable."""
    return CriterionResult(
        pillar="P3",
        index=1,
        name="Lineage graph queryable",
        score=0.0,
        relevance_status=RelevanceStatus.NOT_APPLICABLE,
        confidence_score=0.90,
        evidence="Neptune not provisioned",
        criterion_type=CriterionType.BINARY,
        exclusion_reason="Service not provisioned",
    )


@pytest.fixture
def sample_assessment(
    binary_criterion, binary_criterion_failed, analog_criterion, not_applicable_criterion
) -> ForgeAssessmentResult:
    """A minimal ForgeAssessmentResult with mixed criterion types."""
    pillar_p1 = PillarScore(
        code="P1",
        name="Agent Access & Discovery",
        raw_score=58.33,
        relevant_count=3,
        not_applicable_count=0,
        undetermined_count=0,
        criteria=[binary_criterion, binary_criterion_failed, analog_criterion],
    )
    pillar_p3 = PillarScore(
        code="P3",
        name="Data Lineage & Provenance",
        raw_score=0.0,
        relevant_count=0,
        not_applicable_count=1,
        undetermined_count=0,
        criteria=[not_applicable_criterion],
    )
    return ForgeAssessmentResult(
        metadata={
            "account_id": "123456789012",
            "region": "us-east-1",
            "customer_name": "Test Corp",
            "timestamp": "2025-01-01T00:00:00Z",
            "collector_version": "2.3.0",
        },
        pillars=[pillar_p1, pillar_p3],
        summary={
            "forge_score": 58.3,
            "readiness_band": "GOVERNED",
            "raw_score": 62.0,
            "coverage_multiplier": 0.94,
        },
    )


# --- Tests ---


class TestWrapAwsResult:
    def test_returns_platform_segment(self, sample_assessment):
        """wrap_aws_result returns a PlatformSegment."""
        segment = wrap_aws_result(sample_assessment)
        assert isinstance(segment, PlatformSegment)

    def test_platform_is_aws(self, sample_assessment):
        """Platform identifier is 'aws'."""
        segment = wrap_aws_result(sample_assessment)
        assert segment.platform == "aws"

    def test_source_type_is_api_discovery(self, sample_assessment):
        """Source type is 'api_discovery' for AWS collector results."""
        segment = wrap_aws_result(sample_assessment)
        assert segment.source_type == "api_discovery"

    def test_pillars_preserved(self, sample_assessment):
        """Pillars from the original result are passed through."""
        segment = wrap_aws_result(sample_assessment)
        assert segment.pillars == sample_assessment.pillars

    def test_summary_preserved(self, sample_assessment):
        """Summary dict is preserved as-is."""
        segment = wrap_aws_result(sample_assessment)
        assert segment.summary == sample_assessment.summary

    def test_metadata_preserved(self, sample_assessment):
        """Metadata dict is preserved as-is."""
        segment = wrap_aws_result(sample_assessment)
        assert segment.metadata == sample_assessment.metadata

    def test_criteria_count_matches_all_pillars(self, sample_assessment):
        """Number of criteria in segment equals total criteria across all pillars."""
        segment = wrap_aws_result(sample_assessment)
        total_criteria = sum(len(p.criteria) for p in sample_assessment.pillars)
        assert len(segment.criteria) == total_criteria

    def test_all_criteria_have_platform_aws(self, sample_assessment):
        """Every CriterionSegmentResult has platform='aws'."""
        segment = wrap_aws_result(sample_assessment)
        for cr in segment.criteria:
            assert cr.platform == "aws"

    def test_binary_criterion_no_analog_detail(self, sample_assessment):
        """Binary criteria have analog_detail=None."""
        segment = wrap_aws_result(sample_assessment)
        binary_criteria = [
            cr for cr in segment.criteria if cr.criterion_type == CriterionType.BINARY
        ]
        for cr in binary_criteria:
            assert cr.analog_detail is None

    def test_analog_criterion_has_analog_detail(self, sample_assessment):
        """Analog criteria have analog_detail populated."""
        segment = wrap_aws_result(sample_assessment)
        analog_criteria = [
            cr for cr in segment.criteria if cr.criterion_type == CriterionType.ANALOG
        ]
        assert len(analog_criteria) > 0
        for cr in analog_criteria:
            assert cr.analog_detail is not None
            assert isinstance(cr.analog_detail, AnalogDetail)

    def test_analog_detail_percentage_representation(self, sample_assessment):
        """Analog detail uses percentage: numerator=round(score*100), denominator=100."""
        segment = wrap_aws_result(sample_assessment)
        analog_criteria = [
            cr for cr in segment.criteria if cr.criterion_type == CriterionType.ANALOG
        ]
        for cr in analog_criteria:
            assert cr.analog_detail.denominator == 100
            assert cr.analog_detail.numerator == round(cr.score * 100)
            assert cr.analog_detail.platform == "aws"

    def test_evidence_preserved(self, sample_assessment):
        """Evidence strings are preserved from original criteria."""
        segment = wrap_aws_result(sample_assessment)
        # Find the first binary criterion (P1.1)
        cr = next(c for c in segment.criteria if c.pillar == "P1" and c.index == 1)
        assert cr.evidence == "GetDatabases API succeeded"

    def test_confidence_preserved(self, sample_assessment):
        """Confidence scores are preserved from original criteria."""
        segment = wrap_aws_result(sample_assessment)
        cr = next(c for c in segment.criteria if c.pillar == "P1" and c.index == 1)
        assert cr.confidence_score == 0.95

    def test_relevance_status_preserved(self, sample_assessment):
        """Relevance status is preserved from original criteria."""
        segment = wrap_aws_result(sample_assessment)
        na_cr = next(c for c in segment.criteria if c.pillar == "P3" and c.index == 1)
        assert na_cr.relevance_status == RelevanceStatus.NOT_APPLICABLE

    def test_exclusion_reason_preserved(self, sample_assessment):
        """Exclusion reason is preserved from original criteria."""
        segment = wrap_aws_result(sample_assessment)
        na_cr = next(c for c in segment.criteria if c.pillar == "P3" and c.index == 1)
        assert na_cr.exclusion_reason == "Service not provisioned"

    def test_score_preserved_for_binary(self, sample_assessment):
        """Binary criterion scores are preserved (0.0 or 1.0)."""
        segment = wrap_aws_result(sample_assessment)
        passed = next(c for c in segment.criteria if c.pillar == "P1" and c.index == 1)
        failed = next(c for c in segment.criteria if c.pillar == "P1" and c.index == 2)
        assert passed.score == 1.0
        assert failed.score == 0.0

    def test_score_preserved_for_analog(self, sample_assessment):
        """Analog criterion scores are preserved."""
        segment = wrap_aws_result(sample_assessment)
        analog = next(c for c in segment.criteria if c.pillar == "P1" and c.index == 6)
        assert analog.score == 0.75


class TestEdgeCases:
    def test_empty_pillars(self):
        """Assessment with no pillars produces segment with empty criteria."""
        result = ForgeAssessmentResult(
            metadata={"customer_name": "Empty"},
            pillars=[],
            summary={"forge_score": 0.0},
        )
        segment = wrap_aws_result(result)
        assert segment.criteria == []
        assert segment.pillars == []

    def test_analog_score_zero(self):
        """Analog criterion with score=0.0 gets analog_detail with numerator=0."""
        pillar = PillarScore(
            code="P4",
            name="Data Quality",
            raw_score=0.0,
            relevant_count=1,
            not_applicable_count=0,
            undetermined_count=0,
            criteria=[
                CriterionResult(
                    pillar="P4", index=1, name="DQ coverage",
                    score=0.0, relevance_status=RelevanceStatus.RELEVANT,
                    confidence_score=0.80, evidence="No DQ rules found",
                    criterion_type=CriterionType.ANALOG,
                )
            ],
        )
        result = ForgeAssessmentResult(
            metadata={}, pillars=[pillar], summary={},
        )
        segment = wrap_aws_result(result)
        cr = segment.criteria[0]
        assert cr.analog_detail.numerator == 0
        assert cr.analog_detail.denominator == 100

    def test_analog_score_one(self):
        """Analog criterion with score=1.0 gets analog_detail with numerator=100."""
        pillar = PillarScore(
            code="P4",
            name="Data Quality",
            raw_score=100.0,
            relevant_count=1,
            not_applicable_count=0,
            undetermined_count=0,
            criteria=[
                CriterionResult(
                    pillar="P4", index=1, name="DQ coverage",
                    score=1.0, relevance_status=RelevanceStatus.RELEVANT,
                    confidence_score=0.85, evidence="100% tables have DQ rules",
                    criterion_type=CriterionType.ANALOG,
                )
            ],
        )
        result = ForgeAssessmentResult(
            metadata={}, pillars=[pillar], summary={},
        )
        segment = wrap_aws_result(result)
        cr = segment.criteria[0]
        assert cr.analog_detail.numerator == 100
        assert cr.analog_detail.denominator == 100

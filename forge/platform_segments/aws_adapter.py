"""
FORGE Platform Segments — AWS Adapter

Wraps an existing ForgeAssessmentResult (from the AWS collector) into
a PlatformSegment without modifying the collector's internal logic.
"""
from __future__ import annotations

from typing import Union

from forge.models import (
    AnalogDetail,
    CriterionResult,
    CriterionSegmentResult,
    CriterionType,
    ForgeAssessmentResult,
    PillarScore,
    PlatformSegment,
)


def wrap_aws_result(result: Union[ForgeAssessmentResult, dict]) -> PlatformSegment:
    """Convert an existing AWS ForgeAssessmentResult to a PlatformSegment.

    Accepts either a ForgeAssessmentResult instance or a raw dict (as loaded
    from a JSON file). If a dict is provided, it is deserialized using
    ForgeAssessmentResult.from_dict().

    Maps each CriterionResult to CriterionSegmentResult with platform="aws".
    For ANALOG criteria, extracts analog_detail from the existing score using
    a percentage-based representation (numerator=round(score*100), denominator=100).
    For BINARY criteria, analog_detail is set to None and score maps directly.

    All evidence, confidence, and relevance_status fields are preserved as-is.

    Args:
        result: A complete ForgeAssessmentResult (or JSON dict) from the AWS collector.

    Returns:
        A PlatformSegment representing the AWS platform assessment.
    """
    if isinstance(result, dict):
        result = ForgeAssessmentResult.from_dict(result)

    criteria: list[CriterionSegmentResult] = []

    for pillar in result.pillars:
        for cr in pillar.criteria:
            segment_result = _map_criterion(cr)
            criteria.append(segment_result)

    return PlatformSegment(
        platform="aws",
        source_type="api_discovery",
        pillars=result.pillars,
        criteria=criteria,
        summary=result.summary,
        metadata=result.metadata,
    )


def _map_criterion(cr: CriterionResult) -> CriterionSegmentResult:
    """Map a single CriterionResult to a CriterionSegmentResult.

    For ANALOG criteria: derive AnalogDetail using percentage-based
    representation (numerator=round(score*100), denominator=100).
    For BINARY criteria: analog_detail=None, score is 0.0 or 1.0.

    Args:
        cr: A CriterionResult from the existing AWS assessment.

    Returns:
        A CriterionSegmentResult with platform="aws".
    """
    analog_detail = None
    if cr.criterion_type == CriterionType.ANALOG:
        analog_detail = AnalogDetail(
            numerator=round(cr.score * 100),
            denominator=100,
            platform="aws",
        )

    return CriterionSegmentResult(
        pillar=cr.pillar,
        index=cr.index,
        name=cr.name,
        score=cr.score,
        relevance_status=cr.relevance_status,
        confidence_score=cr.confidence_score,
        evidence=cr.evidence,
        criterion_type=cr.criterion_type,
        platform="aws",
        analog_detail=analog_detail,
        exclusion_reason=cr.exclusion_reason,
    )

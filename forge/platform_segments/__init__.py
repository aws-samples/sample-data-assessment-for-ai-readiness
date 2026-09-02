"""
FORGE Platform Segments — Public API

This module is the public interface for multi-platform assessment scoring.
It re-exports the core data structures and provides functions for wrapping
existing AWS results and building combined estate results.
"""

from forge.models import (
    AnalogDetail,
    CriterionSegmentResult,
    EstateAssessmentResult,
    ForgeAssessmentResult,
    PlatformSegment,
)
from forge.platform_segments.aws_adapter import wrap_aws_result

__all__ = [
    # Data structures
    "PlatformSegment",
    "EstateAssessmentResult",
    "AnalogDetail",
    "CriterionSegmentResult",
    # Functions
    "wrap_aws_result",
    "build_estate_result",
]


def build_estate_result(
    segments: list[PlatformSegment],
    effective_weights: dict,
    effective_floors: dict,
    metadata: dict,
) -> EstateAssessmentResult:
    """Build the combined estate assessment from platform segments.

    Merges criteria across all platform segments using type-aware logic
    (AND for binary, pooled ratio for analog), computes pillar scores from
    the merged criteria, and applies the standard FORGE formula to produce
    the estate score.

    Args:
        segments: List of PlatformSegment objects (one per assessed platform).
        effective_weights: Pillar weight mapping from the FORGE profile.
        effective_floors: Pillar floor mapping from the FORGE profile.
        metadata: Assessment metadata (customer_name, timestamp, profile, etc.).

    Returns:
        An EstateAssessmentResult containing segments, merged results, and
        the overall estate score.
    """
    raise NotImplementedError(
        "build_estate_result will be implemented after the merge engine (task 2.x)"
    )

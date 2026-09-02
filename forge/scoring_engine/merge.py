"""
FORGE 2.4 — Criteria Merge Engine

Combines criterion results from multiple platform segments into estate-level
scores using type-aware logic:
  - Binary criteria: AND logic — all relevant platforms must pass
  - Analog criteria: Pooled ratio — sum(numerators) / sum(denominators)

Platforms where a criterion is NOT_APPLICABLE are excluded from the merge.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Optional

from forge.models import (
    AnalogDetail,
    CriterionSegmentResult,
    CriterionType,
    PillarScore,
    PlatformSegment,
    ReadinessBand,
    RelevanceStatus,
)
from forge.scoring_engine.formula import (
    compute_coverage_multiplier,
    compute_forge_score,
    compute_raw_score,
)
from forge.scoring_engine.bands import classify_band
from forge.criteria_registry import PILLAR_NAMES


def merge_criteria(
    segments: list[PlatformSegment],
) -> list[CriterionSegmentResult]:
    """Merge criterion results across all platform segments.

    Binary criteria: AND logic — estate scores 1.0 only if ALL relevant
    platforms score ≥ 0.5; 0.0 otherwise.

    Analog criteria: Pooled ratio — sum(numerators) / sum(denominators)
    across all relevant platforms.

    Criteria that are NOT_APPLICABLE on a platform are excluded from that
    platform's contribution to the merge.

    Single-platform pass-through: if only one segment exists, returns that
    segment's criteria with platform changed to "estate".

    Args:
        segments: List of platform segments to merge (at least one required).

    Returns:
        List of estate-level criterion results with merged scores.

    Raises:
        ValueError: If segments list is empty.
    """
    if not segments:
        raise ValueError(
            "At least one platform segment is required for merging"
        )

    # Single-platform pass-through: return criteria unchanged except platform
    if len(segments) == 1:
        return _single_platform_passthrough(segments[0])

    # Group criteria by (pillar, index) across all segments
    criteria_groups: dict[tuple[str, int], list[CriterionSegmentResult]] = defaultdict(list)
    for segment in segments:
        for criterion in segment.criteria:
            criteria_groups[(criterion.pillar, criterion.index)].append(criterion)

    # Merge each criterion group
    merged: list[CriterionSegmentResult] = []
    for (_pillar, _index), results in sorted(criteria_groups.items()):
        if results[0].criterion_type == CriterionType.BINARY:
            merged.append(_merge_binary_criterion(results))
        else:
            merged.append(_merge_analog_criterion(results))

    return merged


def compute_estate_score(
    merged_criteria: list[CriterionSegmentResult],
    effective_weights: dict[str, float],
    effective_floors: dict[str, int],
) -> tuple[float, ReadinessBand, float, float]:
    """Compute estate FORGE score from merged criteria.

    Builds pillar scores from merged criteria (same logic as _build_pillar_scores
    in collector.py), then applies the standard FORGE formula.

    Args:
        merged_criteria: Estate-level merged criterion results.
        effective_weights: Pillar weights from profile (sum to 100.0).
        effective_floors: Pillar floor thresholds from profile.

    Returns:
        Tuple of (estate_score, estate_band, raw_score, coverage_multiplier).
    """
    pillar_scores = _build_pillar_scores_from_merged(merged_criteria)

    # Build pillar score dict for the formula (only pillars with relevant criteria)
    pillar_score_map: dict[str, float] = {}
    for ps in pillar_scores:
        if ps.relevant_count > 0:
            pillar_score_map[ps.code] = ps.raw_score

    raw_score = compute_raw_score(pillar_score_map, effective_weights)
    coverage_multiplier = compute_coverage_multiplier(pillar_score_map, effective_floors)
    estate_score = compute_forge_score(raw_score, coverage_multiplier)
    estate_band = classify_band(estate_score)

    return estate_score, estate_band, raw_score, coverage_multiplier


# ─── Internal Helpers ──────────────────────────────────────────────────────────


def _single_platform_passthrough(
    segment: PlatformSegment,
) -> list[CriterionSegmentResult]:
    """Return a single segment's criteria with platform set to 'estate'.

    When only one platform exists, the estate score equals the platform score
    exactly, so we just relabel.
    """
    return [
        CriterionSegmentResult(
            pillar=cr.pillar,
            index=cr.index,
            name=cr.name,
            score=cr.score,
            relevance_status=cr.relevance_status,
            confidence_score=cr.confidence_score,
            evidence=cr.evidence,
            criterion_type=cr.criterion_type,
            platform="estate",
            analog_detail=cr.analog_detail,
            exclusion_reason=cr.exclusion_reason,
        )
        for cr in segment.criteria
    ]


def _merge_binary_criterion(
    results: list[CriterionSegmentResult],
) -> CriterionSegmentResult:
    """AND logic: all relevant platforms must pass (score >= 0.5).

    If all platforms are NOT_APPLICABLE, the estate criterion is NOT_APPLICABLE.
    """
    # Use the first result as template for name, pillar, index, criterion_type
    template = results[0]

    relevant = [
        r for r in results
        if r.relevance_status in (RelevanceStatus.RELEVANT, RelevanceStatus.UNDETERMINED)
    ]

    if not relevant:
        # All NOT_APPLICABLE → estate-level NOT_APPLICABLE
        return CriterionSegmentResult(
            pillar=template.pillar,
            index=template.index,
            name=template.name,
            score=0.0,
            relevance_status=RelevanceStatus.NOT_APPLICABLE,
            confidence_score=0.0,
            evidence="All platforms: NOT_APPLICABLE",
            criterion_type=CriterionType.BINARY,
            platform="estate",
            analog_detail=None,
            exclusion_reason="Not applicable on any platform",
        )

    all_pass = all(r.score >= 0.5 for r in relevant)
    failed_platforms = [r.platform for r in relevant if r.score < 0.5]
    passed_platforms = [r.platform for r in relevant if r.score >= 0.5]

    if all_pass:
        evidence = f"All platforms pass ({', '.join(passed_platforms)})"
    else:
        evidence = f"Failed on: {', '.join(failed_platforms)}"

    # Confidence: average of relevant platforms
    avg_confidence = sum(r.confidence_score for r in relevant) / len(relevant)

    return CriterionSegmentResult(
        pillar=template.pillar,
        index=template.index,
        name=template.name,
        score=1.0 if all_pass else 0.0,
        relevance_status=RelevanceStatus.RELEVANT,
        confidence_score=avg_confidence,
        evidence=evidence,
        criterion_type=CriterionType.BINARY,
        platform="estate",
        analog_detail=None,
        exclusion_reason=None,
    )


def _merge_analog_criterion(
    results: list[CriterionSegmentResult],
) -> CriterionSegmentResult:
    """Pooled ratio: sum numerators / sum denominators across relevant platforms.

    If all platforms are NOT_APPLICABLE or no analog_detail is available,
    the estate criterion is NOT_APPLICABLE.
    """
    template = results[0]

    relevant = [
        r for r in results
        if r.relevance_status in (RelevanceStatus.RELEVANT, RelevanceStatus.UNDETERMINED)
        and r.analog_detail is not None
    ]

    if not relevant:
        # All NOT_APPLICABLE or missing analog_detail → estate-level NOT_APPLICABLE
        return CriterionSegmentResult(
            pillar=template.pillar,
            index=template.index,
            name=template.name,
            score=0.0,
            relevance_status=RelevanceStatus.NOT_APPLICABLE,
            confidence_score=0.0,
            evidence="All platforms: NOT_APPLICABLE or missing analog detail",
            criterion_type=CriterionType.ANALOG,
            platform="estate",
            analog_detail=None,
            exclusion_reason="Not applicable on any platform",
        )

    total_numerator = sum(r.analog_detail.numerator for r in relevant)
    total_denominator = sum(r.analog_detail.denominator for r in relevant)

    score = total_numerator / total_denominator if total_denominator > 0 else 0.0

    breakdown = ", ".join(
        f"{r.platform}: {r.analog_detail.numerator}/{r.analog_detail.denominator}"
        for r in relevant
    )
    evidence = f"Pooled: {total_numerator}/{total_denominator} ({breakdown})"

    # Confidence: average of relevant platforms
    avg_confidence = sum(r.confidence_score for r in relevant) / len(relevant)

    return CriterionSegmentResult(
        pillar=template.pillar,
        index=template.index,
        name=template.name,
        score=score,
        relevance_status=RelevanceStatus.RELEVANT,
        confidence_score=avg_confidence,
        evidence=evidence,
        criterion_type=CriterionType.ANALOG,
        platform="estate",
        analog_detail=AnalogDetail(
            numerator=total_numerator,
            denominator=total_denominator,
            platform="estate",
        ),
        exclusion_reason=None,
    )


def _build_pillar_scores_from_merged(
    merged_criteria: list[CriterionSegmentResult],
) -> list[PillarScore]:
    """Build pillar scores from merged criteria.

    Same logic as _build_pillar_scores in collector.py but using
    CriterionSegmentResult instead of CriterionResult.
    """
    # Group criteria by pillar
    pillar_criteria: dict[str, list[CriterionSegmentResult]] = defaultdict(list)
    for cr in merged_criteria:
        pillar_criteria[cr.pillar].append(cr)

    pillars: list[PillarScore] = []
    for code in sorted(PILLAR_NAMES.keys()):
        criteria = pillar_criteria.get(code, [])

        relevant = [
            cr for cr in criteria
            if cr.relevance_status in (RelevanceStatus.RELEVANT, RelevanceStatus.UNDETERMINED)
        ]
        not_applicable = [
            cr for cr in criteria
            if cr.relevance_status == RelevanceStatus.NOT_APPLICABLE
        ]
        undetermined = [
            cr for cr in criteria
            if cr.relevance_status == RelevanceStatus.UNDETERMINED
        ]

        relevant_count = len(relevant)
        not_applicable_count = len(not_applicable)
        undetermined_count = len(undetermined)

        # Compute raw score: average of relevant criterion scores * 100
        if relevant_count > 0:
            score_sum = sum(cr.score for cr in relevant)
            raw_score = round((score_sum / relevant_count) * 100, 2)
        else:
            raw_score = 0.0

        pillars.append(PillarScore(
            code=code,
            name=PILLAR_NAMES.get(code, code),
            raw_score=raw_score,
            relevant_count=relevant_count,
            not_applicable_count=not_applicable_count,
            undetermined_count=undetermined_count,
            criteria=[],  # CriterionSegmentResult != CriterionResult, leave empty
        ))

    return pillars

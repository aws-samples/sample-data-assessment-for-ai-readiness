"""
Property-based tests for the FORGE Criteria Merge Engine.

Uses Hypothesis to verify merge invariants across randomized platform segments.

Properties tested:
  1. Single-platform backward compatibility (Req 3.5)
  2. Binary merge AND semantics (Req 2.1)
  3. Analog merge pooled ratio (Req 2.2)
  4. NOT_APPLICABLE exclusion (Req 2.3, 2.4)
  5. Estate score in [0.0, 100.0] (Req 3.1)
  6. Pillar exclusion for empty platforms (Req 1.3)
"""
from __future__ import annotations

from hypothesis import given, settings, assume
from hypothesis.strategies import (
    composite,
    floats,
    integers,
    lists,
    sampled_from,
    text,
)

from forge.models import (
    AnalogDetail,
    CriterionSegmentResult,
    CriterionType,
    PillarScore,
    PlatformSegment,
    RelevanceStatus,
)
from forge.scoring_engine.merge import merge_criteria, _build_pillar_scores_from_merged


# ─── Strategies ────────────────────────────────────────────────────────────────

valid_score = floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
binary_score = sampled_from([0.0, 1.0])
platform_names = sampled_from(["aws", "databricks", "azure", "snowflake"])
pillar_codes = sampled_from(["P1", "P2", "P3", "P4", "P5", "P6", "P7", "P8", "P9"])
confidence_score = floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)


@composite
def binary_criterion(draw, pillar=None, index=None, platform=None):
    """Generate a random BINARY CriterionSegmentResult."""
    return CriterionSegmentResult(
        pillar=draw(pillar_codes) if pillar is None else pillar,
        index=draw(integers(min_value=1, max_value=5)) if index is None else index,
        name="Test Binary Criterion",
        score=draw(binary_score),
        relevance_status=RelevanceStatus.RELEVANT,
        confidence_score=draw(confidence_score),
        evidence="Test evidence",
        criterion_type=CriterionType.BINARY,
        platform=draw(platform_names) if platform is None else platform,
    )


@composite
def analog_criterion(draw, pillar=None, index=None, platform=None):
    """Generate a random ANALOG CriterionSegmentResult with AnalogDetail."""
    p = draw(platform_names) if platform is None else platform
    numerator = draw(integers(min_value=0, max_value=1000))
    denominator = draw(integers(min_value=1, max_value=1000))
    score = numerator / denominator if denominator > 0 else 0.0
    # Clamp score to [0, 1]
    score = min(score, 1.0)

    return CriterionSegmentResult(
        pillar=draw(pillar_codes) if pillar is None else pillar,
        index=draw(integers(min_value=1, max_value=5)) if index is None else index,
        name="Test Analog Criterion",
        score=score,
        relevance_status=RelevanceStatus.RELEVANT,
        confidence_score=draw(confidence_score),
        evidence="Test evidence",
        criterion_type=CriterionType.ANALOG,
        platform=p,
        analog_detail=AnalogDetail(
            numerator=numerator,
            denominator=denominator,
            platform=p,
        ),
    )


@composite
def platform_segment(draw, platform=None, criteria=None):
    """Generate a random PlatformSegment with given or random criteria."""
    p = draw(platform_names) if platform is None else platform
    if criteria is None:
        # Generate a mix of binary and analog criteria
        binary_criteria = draw(lists(binary_criterion(platform=p), min_size=1, max_size=5))
        analog_criteria = draw(lists(analog_criterion(platform=p), min_size=0, max_size=3))
        all_criteria = binary_criteria + analog_criteria
    else:
        all_criteria = criteria

    return PlatformSegment(
        platform=p,
        source_type="api_discovery",
        pillars=[],  # Not needed for merge_criteria
        criteria=all_criteria,
        summary={"forge_score": 50.0, "band": "GOVERNED"},
        metadata={},
    )


# ─── Property 1: Single-platform backward compatibility ───────────────────────
# Validates: Requirement 3.5


class TestProperty1SinglePlatformBackwardCompat:
    """**Validates: Requirements 3.5**

    For any assessment with exactly one platform segment, merge_criteria
    returns that segment's criteria with platform="estate" but same scores.
    """

    @given(segment=platform_segment())
    @settings(max_examples=100)
    def test_single_platform_scores_preserved(self, segment: PlatformSegment):
        """Single-platform merge preserves all criterion scores exactly."""
        merged = merge_criteria([segment])

        assert len(merged) == len(segment.criteria)
        for original, estate in zip(segment.criteria, merged):
            assert estate.platform == "estate"
            assert estate.score == original.score
            assert estate.pillar == original.pillar
            assert estate.index == original.index
            assert estate.criterion_type == original.criterion_type
            assert estate.relevance_status == original.relevance_status

    @given(segment=platform_segment())
    @settings(max_examples=100)
    def test_single_platform_analog_detail_preserved(self, segment: PlatformSegment):
        """Single-platform merge preserves analog_detail."""
        merged = merge_criteria([segment])

        for original, estate in zip(segment.criteria, merged):
            if original.analog_detail is not None:
                assert estate.analog_detail is not None
                assert estate.analog_detail.numerator == original.analog_detail.numerator
                assert estate.analog_detail.denominator == original.analog_detail.denominator


# ─── Property 2: Binary merge AND semantics ───────────────────────────────────
# Validates: Requirement 2.1


class TestProperty2BinaryMergeAND:
    """**Validates: Requirements 2.1**

    For any binary criterion across N platforms (N >= 1), estate score is 1.0
    iff ALL relevant platforms score >= 0.5, and 0.0 otherwise.
    """

    @given(
        scores=lists(binary_score, min_size=1, max_size=5),
    )
    @settings(max_examples=100)
    def test_binary_and_semantics(self, scores: list[float]):
        """Binary criterion merge follows AND logic across platforms."""
        platforms = ["aws", "databricks", "azure", "snowflake", "gcp"][:len(scores)]
        criteria_per_platform = []
        for i, (score, plat) in enumerate(zip(scores, platforms)):
            criteria_per_platform.append(
                CriterionSegmentResult(
                    pillar="P1",
                    index=1,
                    name="Test Binary",
                    score=score,
                    relevance_status=RelevanceStatus.RELEVANT,
                    confidence_score=0.8,
                    evidence="test",
                    criterion_type=CriterionType.BINARY,
                    platform=plat,
                )
            )

        segments = [
            PlatformSegment(
                platform=plat,
                source_type="api_discovery",
                pillars=[],
                criteria=[cr],
                summary={},
                metadata={},
            )
            for plat, cr in zip(platforms, criteria_per_platform)
        ]

        merged = merge_criteria(segments)
        assert len(merged) == 1

        estate_criterion = merged[0]
        all_pass = all(s >= 0.5 for s in scores)

        if all_pass:
            assert estate_criterion.score == 1.0
        else:
            assert estate_criterion.score == 0.0

    @given(
        passing_count=integers(min_value=1, max_value=4),
    )
    @settings(max_examples=100)
    def test_binary_all_pass_gives_one(self, passing_count: int):
        """When all platforms pass (score=1.0), estate score is 1.0."""
        platforms = ["aws", "databricks", "azure", "snowflake"][:passing_count]
        segments = [
            PlatformSegment(
                platform=plat,
                source_type="api_discovery",
                pillars=[],
                criteria=[
                    CriterionSegmentResult(
                        pillar="P1", index=1, name="Test",
                        score=1.0,
                        relevance_status=RelevanceStatus.RELEVANT,
                        confidence_score=0.9,
                        evidence="pass",
                        criterion_type=CriterionType.BINARY,
                        platform=plat,
                    )
                ],
                summary={},
                metadata={},
            )
            for plat in platforms
        ]

        merged = merge_criteria(segments)
        assert merged[0].score == 1.0

    @given(
        fail_platform=sampled_from(["aws", "databricks", "azure"]),
    )
    @settings(max_examples=100)
    def test_binary_any_fail_gives_zero(self, fail_platform: str):
        """When any platform fails (score=0.0), estate score is 0.0."""
        platforms = ["aws", "databricks", "azure"]
        segments = [
            PlatformSegment(
                platform=plat,
                source_type="api_discovery",
                pillars=[],
                criteria=[
                    CriterionSegmentResult(
                        pillar="P1", index=1, name="Test",
                        score=0.0 if plat == fail_platform else 1.0,
                        relevance_status=RelevanceStatus.RELEVANT,
                        confidence_score=0.9,
                        evidence="test",
                        criterion_type=CriterionType.BINARY,
                        platform=plat,
                    )
                ],
                summary={},
                metadata={},
            )
            for plat in platforms
        ]

        merged = merge_criteria(segments)
        assert merged[0].score == 0.0


# ─── Property 3: Analog merge pooled ratio ────────────────────────────────────
# Validates: Requirement 2.2


class TestProperty3AnalogMergePooledRatio:
    """**Validates: Requirements 2.2**

    For any analog criterion with AnalogDetail on N platforms, estate score
    equals sum(numerators) / sum(denominators), and the result is in [0.0, 1.0].
    """

    @given(
        numerators=lists(integers(min_value=0, max_value=500), min_size=1, max_size=5),
        denominators=lists(integers(min_value=1, max_value=500), min_size=1, max_size=5),
    )
    @settings(max_examples=100)
    def test_analog_pooled_ratio(self, numerators: list[int], denominators: list[int]):
        """Analog merge computes sum(numerators) / sum(denominators)."""
        # Ensure lists are same length
        min_len = min(len(numerators), len(denominators))
        numerators = numerators[:min_len]
        denominators = denominators[:min_len]

        # Ensure numerator <= denominator for valid ratios
        capped_numerators = [min(n, d) for n, d in zip(numerators, denominators)]

        platforms = ["aws", "databricks", "azure", "snowflake", "gcp"][:min_len]

        segments = []
        for plat, num, den in zip(platforms, capped_numerators, denominators):
            score = num / den
            segments.append(
                PlatformSegment(
                    platform=plat,
                    source_type="api_discovery",
                    pillars=[],
                    criteria=[
                        CriterionSegmentResult(
                            pillar="P4", index=2, name="Test Analog",
                            score=score,
                            relevance_status=RelevanceStatus.RELEVANT,
                            confidence_score=0.8,
                            evidence="test",
                            criterion_type=CriterionType.ANALOG,
                            platform=plat,
                            analog_detail=AnalogDetail(
                                numerator=num,
                                denominator=den,
                                platform=plat,
                            ),
                        )
                    ],
                    summary={},
                    metadata={},
                )
            )

        merged = merge_criteria(segments)
        assert len(merged) == 1

        estate_criterion = merged[0]
        expected_score = sum(capped_numerators) / sum(denominators)

        assert abs(estate_criterion.score - expected_score) < 1e-9
        assert 0.0 <= estate_criterion.score <= 1.0

    @given(
        numerators=lists(integers(min_value=0, max_value=500), min_size=2, max_size=4),
        denominators=lists(integers(min_value=1, max_value=500), min_size=2, max_size=4),
    )
    @settings(max_examples=100)
    def test_analog_detail_sums_correct(self, numerators: list[int], denominators: list[int]):
        """Merged analog_detail has correct summed numerator and denominator."""
        min_len = min(len(numerators), len(denominators))
        numerators = numerators[:min_len]
        denominators = denominators[:min_len]
        capped_numerators = [min(n, d) for n, d in zip(numerators, denominators)]

        platforms = ["aws", "databricks", "azure", "snowflake"][:min_len]

        segments = []
        for plat, num, den in zip(platforms, capped_numerators, denominators):
            segments.append(
                PlatformSegment(
                    platform=plat,
                    source_type="api_discovery",
                    pillars=[],
                    criteria=[
                        CriterionSegmentResult(
                            pillar="P4", index=2, name="Test Analog",
                            score=num / den,
                            relevance_status=RelevanceStatus.RELEVANT,
                            confidence_score=0.8,
                            evidence="test",
                            criterion_type=CriterionType.ANALOG,
                            platform=plat,
                            analog_detail=AnalogDetail(
                                numerator=num, denominator=den, platform=plat,
                            ),
                        )
                    ],
                    summary={},
                    metadata={},
                )
            )

        merged = merge_criteria(segments)
        estate_criterion = merged[0]

        assert estate_criterion.analog_detail is not None
        assert estate_criterion.analog_detail.numerator == sum(capped_numerators)
        assert estate_criterion.analog_detail.denominator == sum(denominators)
        assert estate_criterion.analog_detail.platform == "estate"


# ─── Property 4: NOT_APPLICABLE exclusion ─────────────────────────────────────
# Validates: Requirements 2.3, 2.4


class TestProperty4NotApplicableExclusion:
    """**Validates: Requirements 2.3, 2.4**

    Criteria that are NOT_APPLICABLE on a platform are excluded from that
    platform's contribution to the merge. NOT_APPLICABLE platforms don't count
    as failures.
    """

    @given(
        relevant_score=binary_score,
    )
    @settings(max_examples=100)
    def test_na_platform_excluded_from_binary(self, relevant_score: float):
        """NOT_APPLICABLE platform doesn't affect binary merge outcome."""
        # AWS is RELEVANT, Databricks is NOT_APPLICABLE
        segments = [
            PlatformSegment(
                platform="aws",
                source_type="api_discovery",
                pillars=[],
                criteria=[
                    CriterionSegmentResult(
                        pillar="P1", index=1, name="Test",
                        score=relevant_score,
                        relevance_status=RelevanceStatus.RELEVANT,
                        confidence_score=0.9,
                        evidence="aws result",
                        criterion_type=CriterionType.BINARY,
                        platform="aws",
                    )
                ],
                summary={},
                metadata={},
            ),
            PlatformSegment(
                platform="databricks",
                source_type="conversational",
                pillars=[],
                criteria=[
                    CriterionSegmentResult(
                        pillar="P1", index=1, name="Test",
                        score=0.0,  # Would be failure if counted
                        relevance_status=RelevanceStatus.NOT_APPLICABLE,
                        confidence_score=0.0,
                        evidence="N/A on databricks",
                        criterion_type=CriterionType.BINARY,
                        platform="databricks",
                        exclusion_reason="Service not used",
                    )
                ],
                summary={},
                metadata={},
            ),
        ]

        merged = merge_criteria(segments)
        assert len(merged) == 1

        # Estate score should reflect only the RELEVANT platform (AWS)
        estate = merged[0]
        if relevant_score >= 0.5:
            assert estate.score == 1.0
        else:
            assert estate.score == 0.0

    @given(
        num=integers(min_value=0, max_value=500),
        den=integers(min_value=1, max_value=500),
    )
    @settings(max_examples=100)
    def test_na_platform_excluded_from_analog(self, num: int, den: int):
        """NOT_APPLICABLE platform doesn't affect analog pooled ratio."""
        num = min(num, den)  # Ensure valid ratio

        segments = [
            PlatformSegment(
                platform="aws",
                source_type="api_discovery",
                pillars=[],
                criteria=[
                    CriterionSegmentResult(
                        pillar="P4", index=2, name="Test Analog",
                        score=num / den,
                        relevance_status=RelevanceStatus.RELEVANT,
                        confidence_score=0.8,
                        evidence="aws result",
                        criterion_type=CriterionType.ANALOG,
                        platform="aws",
                        analog_detail=AnalogDetail(numerator=num, denominator=den, platform="aws"),
                    )
                ],
                summary={},
                metadata={},
            ),
            PlatformSegment(
                platform="databricks",
                source_type="conversational",
                pillars=[],
                criteria=[
                    CriterionSegmentResult(
                        pillar="P4", index=2, name="Test Analog",
                        score=0.0,
                        relevance_status=RelevanceStatus.NOT_APPLICABLE,
                        confidence_score=0.0,
                        evidence="N/A",
                        criterion_type=CriterionType.ANALOG,
                        platform="databricks",
                        analog_detail=AnalogDetail(numerator=0, denominator=100, platform="databricks"),
                    )
                ],
                summary={},
                metadata={},
            ),
        ]

        merged = merge_criteria(segments)
        estate = merged[0]

        # Should only use AWS's numbers
        expected_score = num / den
        assert abs(estate.score - expected_score) < 1e-9

    @settings(max_examples=100)
    @given(
        num_platforms=integers(min_value=2, max_value=4),
    )
    def test_all_na_gives_na_estate(self, num_platforms: int):
        """When all platforms are NOT_APPLICABLE, estate criterion is NOT_APPLICABLE."""
        platforms = ["aws", "databricks", "azure", "snowflake"][:num_platforms]
        segments = [
            PlatformSegment(
                platform=plat,
                source_type="api_discovery",
                pillars=[],
                criteria=[
                    CriterionSegmentResult(
                        pillar="P1", index=1, name="Test",
                        score=0.0,
                        relevance_status=RelevanceStatus.NOT_APPLICABLE,
                        confidence_score=0.0,
                        evidence="N/A",
                        criterion_type=CriterionType.BINARY,
                        platform=plat,
                        exclusion_reason="Not applicable",
                    )
                ],
                summary={},
                metadata={},
            )
            for plat in platforms
        ]

        merged = merge_criteria(segments)
        assert len(merged) == 1
        assert merged[0].relevance_status == RelevanceStatus.NOT_APPLICABLE


# ─── Property 5: Estate score in [0.0, 100.0] ─────────────────────────────────
# Validates: Requirement 3.1


class TestProperty5EstateScoreRange:
    """**Validates: Requirements 3.1**

    For any set of platform segments with valid criteria, the estate score
    (computed from pillar scores) is always in [0.0, 100.0].
    """

    @given(
        segment=platform_segment(),
    )
    @settings(max_examples=100)
    def test_pillar_scores_in_valid_range(self, segment: PlatformSegment):
        """Pillar scores built from merged criteria are in [0.0, 100.0]."""
        merged = merge_criteria([segment])
        pillar_scores = _build_pillar_scores_from_merged(merged)

        for ps in pillar_scores:
            assert 0.0 <= ps.raw_score <= 100.0

    @given(
        scores=lists(binary_score, min_size=1, max_size=9),
    )
    @settings(max_examples=100)
    def test_binary_pillar_scores_bounded(self, scores: list[float]):
        """Pillar scores from binary criteria are always in [0.0, 100.0]."""
        # Create one binary criterion per pillar
        pillars = ["P1", "P2", "P3", "P4", "P5", "P6", "P7", "P8", "P9"][:len(scores)]
        criteria = [
            CriterionSegmentResult(
                pillar=p, index=1, name=f"Test {p}",
                score=s,
                relevance_status=RelevanceStatus.RELEVANT,
                confidence_score=0.9,
                evidence="test",
                criterion_type=CriterionType.BINARY,
                platform="aws",
            )
            for p, s in zip(pillars, scores)
        ]

        segment = PlatformSegment(
            platform="aws",
            source_type="api_discovery",
            pillars=[],
            criteria=criteria,
            summary={},
            metadata={},
        )

        merged = merge_criteria([segment])
        pillar_scores = _build_pillar_scores_from_merged(merged)

        for ps in pillar_scores:
            assert 0.0 <= ps.raw_score <= 100.0

    @given(
        numerators=lists(integers(min_value=0, max_value=100), min_size=1, max_size=9),
        denominators=lists(integers(min_value=1, max_value=100), min_size=1, max_size=9),
    )
    @settings(max_examples=100)
    def test_analog_pillar_scores_bounded(self, numerators: list[int], denominators: list[int]):
        """Pillar scores from analog criteria are always in [0.0, 100.0]."""
        min_len = min(len(numerators), len(denominators))
        numerators = numerators[:min_len]
        denominators = denominators[:min_len]
        capped = [min(n, d) for n, d in zip(numerators, denominators)]

        pillars = ["P1", "P2", "P3", "P4", "P5", "P6", "P7", "P8", "P9"][:min_len]
        criteria = [
            CriterionSegmentResult(
                pillar=p, index=1, name=f"Test {p}",
                score=n / d,
                relevance_status=RelevanceStatus.RELEVANT,
                confidence_score=0.8,
                evidence="test",
                criterion_type=CriterionType.ANALOG,
                platform="aws",
                analog_detail=AnalogDetail(numerator=n, denominator=d, platform="aws"),
            )
            for p, n, d in zip(pillars, capped, denominators)
        ]

        segment = PlatformSegment(
            platform="aws",
            source_type="api_discovery",
            pillars=[],
            criteria=criteria,
            summary={},
            metadata={},
        )

        merged = merge_criteria([segment])
        pillar_scores = _build_pillar_scores_from_merged(merged)

        for ps in pillar_scores:
            assert 0.0 <= ps.raw_score <= 100.0


# ─── Property 6: Pillar exclusion for empty platforms ──────────────────────────
# Validates: Requirement 1.3


class TestProperty6PillarExclusionForEmptyPlatforms:
    """**Validates: Requirements 1.3**

    When all criteria in a pillar are NOT_APPLICABLE on a platform, that
    pillar should have relevant_count=0 in the built pillar scores.
    """

    @given(
        na_pillar=pillar_codes,
        num_criteria=integers(min_value=1, max_value=5),
    )
    @settings(max_examples=100)
    def test_all_na_pillar_has_zero_relevant(self, na_pillar: str, num_criteria: int):
        """A pillar with all NOT_APPLICABLE criteria has relevant_count=0."""
        criteria = [
            CriterionSegmentResult(
                pillar=na_pillar,
                index=i,
                name=f"Criterion {i}",
                score=0.0,
                relevance_status=RelevanceStatus.NOT_APPLICABLE,
                confidence_score=0.0,
                evidence="N/A",
                criterion_type=CriterionType.BINARY,
                platform="aws",
                exclusion_reason="Service not provisioned",
            )
            for i in range(1, num_criteria + 1)
        ]

        segment = PlatformSegment(
            platform="aws",
            source_type="api_discovery",
            pillars=[],
            criteria=criteria,
            summary={},
            metadata={},
        )

        merged = merge_criteria([segment])
        pillar_scores = _build_pillar_scores_from_merged(merged)

        # Find the target pillar
        target_pillar = next(
            (ps for ps in pillar_scores if ps.code == na_pillar), None
        )
        assert target_pillar is not None
        assert target_pillar.relevant_count == 0
        assert target_pillar.not_applicable_count == num_criteria

    @given(
        na_pillar=pillar_codes,
        relevant_pillar=pillar_codes,
        relevant_score=valid_score,
    )
    @settings(max_examples=100)
    def test_mixed_pillars_na_excluded_relevant_counted(
        self, na_pillar: str, relevant_pillar: str, relevant_score: float,
    ):
        """NA pillar has relevant_count=0 while other pillars count normally."""
        assume(na_pillar != relevant_pillar)

        criteria = [
            # NA pillar criterion
            CriterionSegmentResult(
                pillar=na_pillar,
                index=1,
                name="NA Criterion",
                score=0.0,
                relevance_status=RelevanceStatus.NOT_APPLICABLE,
                confidence_score=0.0,
                evidence="N/A",
                criterion_type=CriterionType.BINARY,
                platform="aws",
                exclusion_reason="Not applicable",
            ),
            # Relevant pillar criterion
            CriterionSegmentResult(
                pillar=relevant_pillar,
                index=1,
                name="Relevant Criterion",
                score=relevant_score,
                relevance_status=RelevanceStatus.RELEVANT,
                confidence_score=0.9,
                evidence="test",
                criterion_type=CriterionType.BINARY,
                platform="aws",
            ),
        ]

        segment = PlatformSegment(
            platform="aws",
            source_type="api_discovery",
            pillars=[],
            criteria=criteria,
            summary={},
            metadata={},
        )

        merged = merge_criteria([segment])
        pillar_scores = _build_pillar_scores_from_merged(merged)

        na_ps = next((ps for ps in pillar_scores if ps.code == na_pillar), None)
        relevant_ps = next((ps for ps in pillar_scores if ps.code == relevant_pillar), None)

        assert na_ps is not None
        assert na_ps.relevant_count == 0

        assert relevant_ps is not None
        assert relevant_ps.relevant_count == 1

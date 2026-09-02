"""Unit tests for forge.scoring_engine.formula (v2.3)."""

import pytest

from forge.scoring_engine.formula import (
    PENALTY_CAP,
    PILLAR_PENALTY_RATES,
    compute_coverage_multiplier,
    compute_forge_score,
    compute_raw_score,
)


# --- Fixtures ---

@pytest.fixture
def equal_weights() -> dict[str, float]:
    """Equal weights across 9 pillars summing to 100%."""
    w = 100.0 / 9
    return {f"P{i}": w for i in range(1, 10)}


@pytest.fixture
def sample_weights() -> dict[str, float]:
    """Sample effective weights summing to 100.0."""
    return {
        "P1": 18.5, "P2": 19.2, "P3": 9.3, "P4": 13.0,
        "P5": 12.0, "P6": 8.0, "P7": 6.5, "P8": 9.0, "P9": 4.5,
    }


@pytest.fixture
def baseline_floors() -> dict[str, int]:
    """Baseline effective floors (all 25)."""
    return {f"P{i}": 25 for i in range(1, 10)}


@pytest.fixture
def elevated_floors() -> dict[str, int]:
    """Elevated effective floors for testing penalty logic."""
    return {
        "P1": 35, "P2": 40, "P3": 30,
        "P4": 30, "P5": 35, "P6": 25,
        "P7": 25, "P8": 25, "P9": 25,
    }


# --- compute_raw_score tests ---

class TestComputeRawScore:
    def test_all_pillars_100(self, equal_weights):
        """All pillars at 100% should yield raw score of 100."""
        scores = {f"P{i}": 100.0 for i in range(1, 10)}
        result = compute_raw_score(scores, equal_weights)
        assert abs(result - 100.0) < 0.01

    def test_all_pillars_zero(self, equal_weights):
        """All pillars at 0 should yield raw score of 0."""
        scores = {f"P{i}": 0.0 for i in range(1, 10)}
        result = compute_raw_score(scores, equal_weights)
        assert result == 0.0

    def test_weighted_sum_correctness(self, sample_weights):
        """Verify weighted sum formula: sum(score * weight / 100)."""
        scores = {
            "P1": 80.0, "P2": 60.0, "P3": 50.0, "P4": 70.0,
            "P5": 65.0, "P6": 40.0, "P7": 55.0, "P8": 45.0, "P9": 30.0,
        }
        expected = sum(
            scores[p] * sample_weights[p] / 100 for p in sample_weights
        )
        result = compute_raw_score(scores, sample_weights)
        assert abs(result - expected) < 0.001

    def test_missing_pillar_scores_treated_as_zero(self, sample_weights):
        """Pillar missing from scores dict uses 0.0."""
        scores = {"P1": 100.0}  # Only P1 provided
        expected = 100.0 * sample_weights["P1"] / 100
        result = compute_raw_score(scores, sample_weights)
        assert abs(result - expected) < 0.001

    def test_rejects_empty_weights(self):
        """Empty weights should raise ValueError."""
        with pytest.raises(ValueError, match="must not be empty"):
            compute_raw_score({"P1": 50.0}, {})

    def test_rejects_weights_not_summing_to_100(self):
        """Weights not summing to ~100 should raise ValueError."""
        bad_weights = {f"P{i}": 10.0 for i in range(1, 10)}  # sums to 90
        with pytest.raises(ValueError, match="must sum to 100.0%"):
            compute_raw_score({"P1": 50.0}, bad_weights)

    def test_accepts_weights_within_tolerance(self):
        """Weights summing to 99.95 or 100.05 should be accepted."""
        # 9 * 11.11 = 99.99 — within ±0.1 tolerance
        weights = {f"P{i}": 100.0 / 9 for i in range(1, 10)}
        scores = {f"P{i}": 50.0 for i in range(1, 10)}
        # Should not raise
        result = compute_raw_score(scores, weights)
        assert 49.0 < result < 51.0


# --- compute_coverage_multiplier tests ---

class TestComputeCoverageMultiplier:
    def test_no_penalty_all_above_floor(self, baseline_floors):
        """All pillars above floor → multiplier = 1.0."""
        scores = {f"P{i}": 50.0 for i in range(1, 10)}
        result = compute_coverage_multiplier(scores, baseline_floors)
        assert result == 1.0

    def test_no_penalty_at_exact_floor(self, baseline_floors):
        """Pillar scoring EXACTLY at floor → no penalty (strictly below)."""
        scores = {f"P{i}": 25.0 for i in range(1, 10)}
        result = compute_coverage_multiplier(scores, baseline_floors)
        assert result == 1.0

    def test_penalty_below_floor(self, baseline_floors):
        """Single pillar below floor → applies that pillar's penalty rate."""
        scores = {f"P{i}": 50.0 for i in range(1, 10)}
        scores["P1"] = 24.9  # Just below the 25 floor
        expected = 1.0 - (PILLAR_PENALTY_RATES["P1"] / 100)
        result = compute_coverage_multiplier(scores, baseline_floors)
        assert abs(result - expected) < 0.001

    def test_penalty_capped_at_40(self, baseline_floors):
        """All pillars below floor → penalty capped at 40%, multiplier = 0.60."""
        scores = {f"P{i}": 0.0 for i in range(1, 10)}
        result = compute_coverage_multiplier(scores, baseline_floors)
        # Total penalty without cap: 8+8+8+5+5+5+5+5+3 = 52 > 40
        assert result == 0.60

    def test_elevated_floors_penalty(self, elevated_floors):
        """Elevated floors with some pillars below → correct penalty."""
        scores = {
            "P1": 30.0,  # Below 35 → penalty 8
            "P2": 40.0,  # AT 40 → no penalty (exactly at floor)
            "P3": 25.0,  # Below 30 → penalty 8
            "P4": 30.0,  # AT 30 → no penalty
            "P5": 30.0,  # Below 35 → penalty 5
            "P6": 50.0,  # Above 25 → no penalty
            "P7": 50.0,  # Above 25 → no penalty
            "P8": 50.0,  # Above 25 → no penalty
            "P9": 50.0,  # Above 25 → no penalty
        }
        expected_penalty = 8 + 8 + 5  # P1 + P3 + P5
        expected = 1.0 - (expected_penalty / 100)
        result = compute_coverage_multiplier(scores, elevated_floors)
        assert abs(result - expected) < 0.001

    def test_rejects_empty_floors(self):
        """Empty floors should raise ValueError."""
        with pytest.raises(ValueError, match="must not be empty"):
            compute_coverage_multiplier({"P1": 50.0}, {})

    def test_rejects_floor_below_25(self):
        """Floor below 25 should raise ValueError."""
        bad_floors = {"P1": 24}
        with pytest.raises(ValueError, match="outside valid range"):
            compute_coverage_multiplier({"P1": 50.0}, bad_floors)

    def test_rejects_floor_above_100(self):
        """Floor above 100 should raise ValueError."""
        bad_floors = {"P1": 101}
        with pytest.raises(ValueError, match="outside valid range"):
            compute_coverage_multiplier({"P1": 50.0}, bad_floors)


# --- compute_forge_score tests ---

class TestComputeForgeScore:
    def test_simple_multiply_and_round(self):
        """FORGE Score = raw * multiplier, rounded to 1 decimal."""
        assert compute_forge_score(67.8, 0.92) == 62.4

    def test_perfect_score(self):
        """100 raw × 1.0 multiplier = 100.0."""
        assert compute_forge_score(100.0, 1.0) == 100.0

    def test_zero_score(self):
        """0 raw × any multiplier = 0.0."""
        assert compute_forge_score(0.0, 0.85) == 0.0

    def test_minimum_multiplier(self):
        """Score with minimum multiplier (0.60)."""
        result = compute_forge_score(80.0, 0.60)
        assert result == 48.0

    def test_rounding_behavior(self):
        """Verify rounding to 1 decimal place."""
        # 55.55 * 0.88 = 48.884 → rounds to 48.9
        result = compute_forge_score(55.55, 0.88)
        assert result == 48.9


# --- Module-level constant checks ---

class TestConstants:
    def test_penalty_rates_cover_all_pillars(self):
        """All 9 pillars should have penalty rates defined."""
        expected_pillars = {f"P{i}" for i in range(1, 10)}
        assert set(PILLAR_PENALTY_RATES.keys()) == expected_pillars

    def test_penalty_rates_values_unchanged(self):
        """Verify penalty rate values match design specification."""
        assert PILLAR_PENALTY_RATES == {
            "P1": 8, "P2": 8, "P3": 8,
            "P4": 5, "P5": 5, "P6": 5, "P7": 5, "P8": 5,
            "P9": 3,
        }

    def test_penalty_cap_is_40(self):
        """PENALTY_CAP should be 40."""
        assert PENALTY_CAP == 40

"""
FORGE 2.3 — Scoring Formula

Implements the FORGE Score calculation:
  FORGE Score = Raw Score × Coverage Multiplier

Raw Score uses effective weights from the Profile Engine (no hardcoded weights).
Coverage Multiplier uses effective floors from the Profile Engine (no hardcoded threshold).
"""

from __future__ import annotations

PILLAR_PENALTY_RATES: dict[str, int] = {
    "P1": 8, "P2": 8, "P3": 8,
    "P4": 5, "P5": 5, "P6": 5, "P7": 5, "P8": 5,
    "P9": 3,
}

PENALTY_CAP = 40  # Maximum cumulative penalty percentage

# Tolerance for weight sum validation (floating-point rounding)
_WEIGHT_SUM_TOLERANCE = 0.1


def _validate_weights(effective_weights: dict[str, float]) -> None:
    """Validate that effective weights sum to ~100% and are positive.

    Raises ValueError if weights don't sum to 100.0 (±0.1 tolerance)
    or if any weight is non-positive.
    """
    if not effective_weights:
        raise ValueError(
            "effective_weights must not be empty; profile resolution is required before scoring"
        )
    weight_sum = sum(effective_weights.values())
    if abs(weight_sum - 100.0) > _WEIGHT_SUM_TOLERANCE:
        raise ValueError(
            f"effective_weights must sum to 100.0% (got {weight_sum:.2f}%); "
            "ensure profile resolution produced valid weights"
        )


def _validate_floors(effective_floors: dict[str, int]) -> None:
    """Validate that effective floors are in the valid range [25, 100].

    Raises ValueError if any floor is outside the valid range or if floors are empty.
    """
    if not effective_floors:
        raise ValueError(
            "effective_floors must not be empty; profile resolution is required before scoring"
        )
    for pillar, floor in effective_floors.items():
        if not (25 <= floor <= 100):
            raise ValueError(
                f"effective_floors[{pillar!r}] = {floor} is outside valid range [25, 100]"
            )


def compute_raw_score(
    pillar_scores: dict[str, float],
    effective_weights: dict[str, float],
) -> float:
    """Compute weighted raw score from pillar percentages using effective weights.

    Args:
        pillar_scores: {"P1": 65.0, "P2": 40.0, ...} — each on 0–100 scale
        effective_weights: {"P1": 18.5, "P2": 19.2, ...} — sum to 100.0

    Returns:
        Weighted sum in 0.0–100.0 range.

    Raises:
        ValueError: If effective_weights don't sum to ~100%.
    """
    _validate_weights(effective_weights)
    return sum(
        pillar_scores.get(code, 0.0) * weight / 100
        for code, weight in effective_weights.items()
    )


def compute_coverage_multiplier(
    pillar_scores: dict[str, float],
    effective_floors: dict[str, int],
) -> float:
    """Compute coverage multiplier penalty for pillars below their effective floor.

    Applies a penalty rate for each pillar scoring STRICTLY below its effective floor.
    A pillar scoring exactly at its floor does NOT incur a penalty.

    Args:
        pillar_scores: {"P1": 65.0, "P2": 20.0, ...} — each on 0–100 scale
        effective_floors: {"P1": 35, "P2": 40, ...} — each in [25, 100]

    Returns:
        Coverage multiplier in [0.60, 1.00] (capped at 40% total penalty).

    Raises:
        ValueError: If effective_floors are invalid.
    """
    _validate_floors(effective_floors)
    penalty = 0
    for pillar, floor in effective_floors.items():
        score = pillar_scores.get(pillar, 0.0)
        if score < floor and pillar in PILLAR_PENALTY_RATES:
            penalty += PILLAR_PENALTY_RATES[pillar]
    penalty = min(penalty, PENALTY_CAP)
    return 1.0 - (penalty / 100)


def compute_forge_score(
    raw_score: float,
    coverage_multiplier: float,
) -> float:
    """Compute final FORGE Score.

    FORGE Score = Raw Score × Coverage Multiplier

    Args:
        raw_score: Weighted pillar score (0.0–100.0)
        coverage_multiplier: Penalty factor (0.60–1.00)

    Returns:
        Score rounded to 1 decimal place, in range 0.0–100.0.
    """
    return round(raw_score * coverage_multiplier, 1)

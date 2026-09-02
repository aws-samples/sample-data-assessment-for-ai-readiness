"""
FORGE 2.1 — Analog Scoring Functions

Scores individual criteria as either:
- Analog (0.0–1.0): coverage ratio clamped to valid range
- Binary (0 or 1.0): presence/absence detection
"""
from forge.models import CriterionType


def score_criterion(
    criterion_type: CriterionType,
    observed: float,
    total: float,
) -> float:
    """Score a single criterion based on its type.

    For ANALOG criteria: returns observed/total clamped to [0.0, 1.0].
    For BINARY criteria: returns 1.0 if observed > 0, else 0.0.

    Args:
        criterion_type: Whether the criterion is ANALOG or BINARY
        observed: Numerator — the measured value (count, ratio, etc.)
        total: Denominator — the maximum possible value (for analog only)

    Returns:
        Score between 0.0 and 1.0 inclusive
    """
    if criterion_type == CriterionType.BINARY:
        return 1.0 if observed > 0 else 0.0

    # Analog: coverage ratio
    if total <= 0:
        return 0.0
    return max(0.0, min(1.0, observed / total))

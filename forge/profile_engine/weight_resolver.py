"""Effective weight computation for the FORGE Profile Engine.

Resolves a ForgeProfile declaration into effective pillar weights by:
1. Summing shift vectors from all 4 dimensions per pillar
2. Capping each combined adjustment at ±8 percentage points
3. Adding capped shift to base weight, then enforcing a 2% floor
4. Normalizing proportionally to sum to exactly 100.0%
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from forge.profile_engine.dimensions import (
    AGENT_MATURITY_SHIFTS,
    ARCHITECTURE_SHIFTS,
    BASE_WEIGHTS,
    INDUSTRY_SHIFTS,
    WORKLOAD_SHIFTS,
)

if TYPE_CHECKING:
    from forge.profile_engine import ForgeProfile

ADJUSTMENT_CAP = 8  # ±8 percentage points max per pillar
PRE_NORM_FLOOR = 2  # 2% minimum before normalization

PILLARS = ["P1", "P2", "P3", "P4", "P5", "P6", "P7", "P8", "P9"]


def compute_effective_weights(profile: ForgeProfile) -> dict[str, float]:
    """Compute effective pillar weights from a ForgeProfile declaration.

    Algorithm (per Requirement 8.2):
        (a) Sum dimension shifts across all four dimensions per pillar.
        (b) Cap each combined adjustment at ±ADJUSTMENT_CAP pp.
        (c) Add capped shift to base weight, enforce PRE_NORM_FLOOR minimum.
        (d) Normalize proportionally so all weights sum to exactly 100.0%.

    Args:
        profile: A ForgeProfile with architecture, workload, industry,
                 and agent_maturity dimensions set.

    Returns:
        A dict mapping pillar keys (P1–P9) to their effective weight
        as a percentage (float), summing to 100.0%.
    """
    # Step (a): Sum shift vectors from all 4 dimensions per pillar
    arch_shifts = ARCHITECTURE_SHIFTS[profile.architecture]
    workload_shifts = WORKLOAD_SHIFTS[profile.workload]
    industry_shifts = INDUSTRY_SHIFTS[profile.industry]
    maturity_shifts = AGENT_MATURITY_SHIFTS[profile.agent_maturity]

    combined_shifts: dict[str, int] = {}
    for pillar in PILLARS:
        combined_shifts[pillar] = (
            arch_shifts.get(pillar, 0)
            + workload_shifts.get(pillar, 0)
            + industry_shifts.get(pillar, 0)
            + maturity_shifts.get(pillar, 0)
        )

    # Step (b): Cap each combined adjustment at ±8pp
    capped_shifts: dict[str, float] = {}
    for pillar in PILLARS:
        shift = combined_shifts[pillar]
        capped_shifts[pillar] = max(-ADJUSTMENT_CAP, min(ADJUSTMENT_CAP, shift))

    # Step (c): Apply base + capped_shift, enforce 2% floor
    adjusted: dict[str, float] = {}
    for pillar in PILLARS:
        raw = BASE_WEIGHTS[pillar] + capped_shifts[pillar]
        adjusted[pillar] = max(PRE_NORM_FLOOR, raw)

    # Step (d): Normalize proportionally to sum to exactly 100.0%
    total = sum(adjusted.values())
    effective_weights: dict[str, float] = {}
    for pillar in PILLARS:
        effective_weights[pillar] = round(adjusted[pillar] / total * 100.0, 1)

    # Correct any floating-point rounding drift so sum is exactly 100.0
    weight_sum = sum(effective_weights.values())
    if weight_sum != 100.0:
        # Adjust the largest weight to compensate for rounding error
        diff = round(100.0 - weight_sum, 1)
        largest_pillar = max(effective_weights, key=lambda p: effective_weights[p])
        effective_weights[largest_pillar] = round(
            effective_weights[largest_pillar] + diff, 1
        )

    return effective_weights

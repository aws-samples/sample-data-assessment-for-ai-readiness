"""Effective floor computation for the FORGE Profile Engine.

Computes per-pillar effective floor thresholds from a ForgeProfile declaration.
The algorithm: for each pillar, take max(BASELINE_FLOOR, max override across all
4 dimension floor tables).

"""

from __future__ import annotations

from typing import TYPE_CHECKING

from forge.profile_engine.dimensions import (
    AGENT_MATURITY_FLOORS,
    ARCHITECTURE_FLOORS,
    INDUSTRY_FLOORS,
    WORKLOAD_FLOORS,
)

if TYPE_CHECKING:
    from forge.profile_engine import ForgeProfile

BASELINE_FLOOR = 25
PILLARS = ["P1", "P2", "P3", "P4", "P5", "P6", "P7", "P8", "P9"]


def _validate_floor_overrides(overrides: dict[str, int], dimension_name: str) -> None:
    """Validate that all floor override values are in [0, 100] range.

    Raises:
        ValueError: If any override value is outside the valid range.
    """
    for pillar, value in overrides.items():
        if not (0 <= value <= 100):
            raise ValueError(
                f"Floor override for {pillar} in {dimension_name} is {value}, "
                f"must be in range [0, 100]"
            )


def compute_effective_floors(profile: ForgeProfile) -> dict[str, int]:
    """Compute effective floor thresholds for each pillar from a ForgeProfile.

    For each pillar P1–P9:
      1. Collect all floor overrides from the 4 dimension tables
      2. Take the maximum of all collected override values
      3. Apply max(BASELINE_FLOOR, that_maximum) to produce the effective floor
      4. If no dimension provides an override, use BASELINE_FLOOR (25)

    Args:
        profile: A ForgeProfile with architecture, workload, industry,
                 and agent_maturity dimensions.

    Returns:
        A dict mapping pillar names ("P1"–"P9") to their effective floor
        thresholds (integers in range [25, 100]).

    Raises:
        ValueError: If any dimension floor override value is outside [0, 100].
    """
    # Gather floor override dicts for each dimension
    arch_floors = ARCHITECTURE_FLOORS.get(profile.architecture, {})
    workload_floors = WORKLOAD_FLOORS.get(profile.workload, {})
    industry_floors = INDUSTRY_FLOORS.get(profile.industry, {})
    maturity_floors = AGENT_MATURITY_FLOORS.get(profile.agent_maturity, {})

    # Validate all override values are in [0, 100]
    _validate_floor_overrides(arch_floors, "Architecture")
    _validate_floor_overrides(workload_floors, "Workload")
    _validate_floor_overrides(industry_floors, "Industry")
    _validate_floor_overrides(maturity_floors, "AgentMaturity")

    # Compute effective floor for each pillar
    effective_floors: dict[str, int] = {}
    for pillar in PILLARS:
        overrides = [
            floors[pillar]
            for floors in (arch_floors, workload_floors, industry_floors, maturity_floors)
            if pillar in floors
        ]

        if overrides:
            # Take max of all dimension overrides, then apply baseline floor
            effective_floors[pillar] = max(BASELINE_FLOOR, max(overrides))
        else:
            # No dimension provides an override — use baseline
            effective_floors[pillar] = BASELINE_FLOOR

    return effective_floors

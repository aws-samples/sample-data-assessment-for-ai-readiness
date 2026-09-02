"""FORGE Delta Engine — computes deltas between consecutive assessment records.

Public API:
    - PillarDelta: Per-pillar delta with classification
    - BandTransition: Score band transition details
    - DeltaResult: Complete delta computation result
    - PlatformDelta: Per-platform delta for multi-platform assessments
    - EstateDeltaResult: Estate-level delta for multi-platform assessments
    - compute_delta: Compute delta between the two most recent assessments
    - compute_estate_delta: Compute estate-level delta with per-platform breakdown
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class PillarDelta:
    """Delta for a single pillar between two consecutive assessments."""

    pillar: str
    previous: float
    current: float
    delta: float  # rounded to 1 decimal
    classification: str  # "improvement" | "regression" | "unchanged"


@dataclass
class BandTransition:
    """Score band transition between two consecutive assessments."""

    previous_band: str
    current_band: str
    direction: str  # "upgrade" | "downgrade"


@dataclass
class DeltaResult:
    """Complete result of a delta computation between two assessments."""

    score_delta: float  # rounded to 1 decimal
    pillar_deltas: list[PillarDelta]
    band_transition: Optional[BandTransition]
    improved_count: int
    regressed_count: int
    available: bool  # False if < 2 records exist


@dataclass
class PlatformDelta:
    """Delta for a single platform between assessments."""

    platform: str
    previous_score: Optional[float]  # None if newly assessed
    current_score: float
    delta: Optional[float]  # None if newly assessed
    status: str  # "improved", "regressed", "unchanged", "newly_assessed"


@dataclass
class EstateDeltaResult:
    """Delta result for multi-platform estate assessments."""

    available: bool
    estate_score_delta: float
    estate_band_transition: Optional[BandTransition]
    platform_deltas: list["PlatformDelta"]
    pillar_deltas: list[PillarDelta]
    improved_count: int
    regressed_count: int
    new_platforms: list[str]  # Platforms newly appearing


def compute_delta(history_path: Path = Path("forge_output/forge_history.jsonl")) -> DeltaResult:
    """Compute delta between the two most recent assessment records.

    Reads forge_history.jsonl, extracts the two most recent entries,
    and computes score deltas, pillar deltas, and band transitions.

    Args:
        history_path: Path to the JSONL history file.

    Returns:
        DeltaResult with available=False if fewer than 2 records exist.
    """
    from forge.delta_engine.comparator import compute_delta as _compute_delta

    return _compute_delta(history_path)


def compute_estate_delta(history_path: Path = Path("forge_output/forge_history.jsonl")):
    """Compute estate-level delta between the two most recent assessments.

    Handles multi-platform assessments with per-platform deltas and
    new platform detection.

    Args:
        history_path: Path to the JSONL history file.

    Returns:
        EstateDeltaResult with available=False if fewer than 2 records exist.
    """
    from forge.delta_engine.comparator import compute_estate_delta as _compute_estate_delta

    return _compute_estate_delta(history_path)


__all__ = [
    "PillarDelta",
    "BandTransition",
    "DeltaResult",
    "PlatformDelta",
    "EstateDeltaResult",
    "compute_delta",
    "compute_estate_delta",
]

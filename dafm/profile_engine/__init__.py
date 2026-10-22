"""DAFM Profile Engine — public API.

Resolves a DAFM Profile declaration into effective weights and effective floors
for use by the Scoring Engine.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from dafm.profile_engine.dimensions import (
    AgentMaturity,
    Architecture,
    Industry,
    Workload,
)
from dafm.profile_engine.floor_resolver import compute_effective_floors
from dafm.profile_engine.persistence import (
    ProfileLockError,
    ProfileNotFoundError,
    is_locked as _is_locked,
    load_profile as _load_profile,
    save_profile as _save_profile,
)
from dafm.profile_engine.weight_resolver import compute_effective_weights


@dataclass
class DafmProfile:
    """A composite descriptor with four dimensions that determines effective
    pillar weights and floor thresholds."""

    architecture: Architecture
    workload: Workload
    industry: Industry
    agent_maturity: AgentMaturity


@dataclass
class ResolvedProfile:
    """Result of resolving a DafmProfile into effective weights and floors."""

    profile: DafmProfile
    effective_weights: dict[str, float]  # P1..P9 → percentage (sum = 100.0)
    effective_floors: dict[str, int]  # P1..P9 → floor threshold (25–100)


def resolve_profile(profile: DafmProfile) -> ResolvedProfile:
    """Compute effective weights and floors from a profile declaration.

    Delegates weight computation to weight_resolver and floor computation
    to floor_resolver, then bundles results into a ResolvedProfile.
    """
    effective_weights = compute_effective_weights(profile)
    effective_floors = compute_effective_floors(profile)
    return ResolvedProfile(
        profile=profile,
        effective_weights=effective_weights,
        effective_floors=effective_floors,
    )


def load_profile(path: Path = Path("dafm_output/dafm_profile.yaml")) -> DafmProfile:
    """Load a locked profile from disk.

    Raises ProfileNotFoundError if the file does not exist.
    """
    return _load_profile(path)


def lock_profile(
    profile: DafmProfile, path: Path = Path("dafm_output/dafm_profile.yaml")
) -> None:
    """Persist and lock a profile. Raises ProfileLockError if already locked."""
    _save_profile(profile, path)


def is_locked(path: Path = Path("dafm_output/dafm_profile.yaml")) -> bool:
    """Check if a profile is locked for the current engagement."""
    return _is_locked(path)


__all__ = [
    "AgentMaturity",
    "Architecture",
    "DafmProfile",
    "Industry",
    "ProfileLockError",
    "ProfileNotFoundError",
    "ResolvedProfile",
    "Workload",
    "is_locked",
    "load_profile",
    "lock_profile",
    "resolve_profile",
]

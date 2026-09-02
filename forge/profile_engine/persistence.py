"""YAML persistence and lock enforcement for FORGE Profiles.

Handles reading, writing, and locking forge_profile.yaml. Once a profile
is persisted it is automatically locked — subsequent modification attempts
are rejected with ProfileLockError.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import yaml

from forge.profile_engine.dimensions import (
    AgentMaturity,
    Architecture,
    Industry,
    Workload,
)


class ProfileLockError(Exception):
    """Raised when trying to modify a locked profile."""


class ProfileNotFoundError(Exception):
    """Raised when the profile file does not exist."""


def save_profile(profile: "ForgeProfile", path: Path = Path("forge_output/forge_profile.yaml")) -> None:
    """Persist a ForgeProfile to YAML with locked state.

    If the file already exists and is locked, raises ProfileLockError.
    Writes the profile with ``locked: true`` and the current UTC timestamp.
    """
    if path.exists() and is_locked(path):
        raise ProfileLockError(
            f"Profile is locked for the current engagement. Cannot modify {path}."
        )

    data = {
        "profile": {
            "architecture": profile.architecture.value,
            "workload": profile.workload.value,
            "industry": profile.industry.value,
            "agent_maturity": profile.agent_maturity.value,
        },
        "locked": True,
        "locked_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False))


def load_profile(path: Path = Path("forge_output/forge_profile.yaml")) -> "ForgeProfile":
    """Load a ForgeProfile from a YAML file.

    Raises ProfileNotFoundError if the file does not exist.
    """
    if not path.exists():
        raise ProfileNotFoundError(
            f"Profile not found at {path}. Declare a profile before proceeding."
        )

    data = yaml.safe_load(path.read_text())
    profile_data = data["profile"]

    # Import here to avoid circular imports at module level
    from forge.profile_engine import ForgeProfile

    return ForgeProfile(
        architecture=Architecture(profile_data["architecture"]),
        workload=Workload(profile_data["workload"]),
        industry=Industry(profile_data["industry"]),
        agent_maturity=AgentMaturity(profile_data["agent_maturity"]),
    )


def is_locked(path: Path = Path("forge_output/forge_profile.yaml")) -> bool:
    """Check whether the profile at the given path is locked.

    Returns False if the file does not exist.
    """
    if not path.exists():
        return False

    data = yaml.safe_load(path.read_text())
    return bool(data.get("locked", False))

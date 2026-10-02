"""
FORGE — Tag Taxonomy Loader

Loads the authoritative tagging taxonomy (``forge_config/tag_taxonomy.yaml``,
v0.2) that describes:

* ``readiness_vectors`` — the FORGE readiness vectors a criterion can carry,
  each mapped to a FORGE letter (F/O/R/G/E).
* ``tensions`` — the design trade-offs a criterion may sit on.
* ``compliance_frameworks`` — the catalog of regulatory frameworks a
  criterion may be relevant to.
* ``tco_indicator`` — the grounding and formula for the 1–5 TCO indicator.
* ``quadrant`` — default axis/size/color mappings for the AI-readiness
  quadrant dashboard view.
* ``pillars`` — per-pillar metadata (name, criteria count, primary/secondary
  vectors).

The loader is dependency-light: it uses the repo's existing PyYAML dependency
and resolves the config file the same way the Profile Engine does (CWD-relative
first, then relative to the package root). It is intentionally forgiving —
callers get an empty dict rather than an exception if the file is missing or
PyYAML is unavailable — mirroring the fallback behaviour elsewhere in the repo.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Optional


def _candidate_paths() -> list[Path]:
    """Return candidate locations for ``tag_taxonomy.yaml`` in priority order."""
    return [
        Path("forge_config/tag_taxonomy.yaml"),
        Path(__file__).resolve().parent.parent
        / "forge_config"
        / "tag_taxonomy.yaml",
    ]


@lru_cache(maxsize=1)
def load_taxonomy() -> dict:
    """Load and return the tag taxonomy as a plain dict.

    Returns:
        The parsed taxonomy dict, or an empty dict if the file cannot be
        found or PyYAML is not installed. The result is cached; callers that
        need to pick up on-disk edits should call ``load_taxonomy.cache_clear()``.
    """
    config_path: Optional[Path] = None
    for candidate in _candidate_paths():
        if candidate.exists():
            config_path = candidate
            break

    if config_path is None:
        return {}

    try:
        import yaml
    except ImportError:
        return {}

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except (OSError, yaml.YAMLError):
        return {}

    return data or {}


def list_vectors() -> dict:
    """Return the ``readiness_vectors`` mapping (vector_key -> metadata dict)."""
    return load_taxonomy().get("readiness_vectors", {})


def list_tensions() -> dict:
    """Return the ``tensions`` mapping (tension_key -> metadata dict)."""
    return load_taxonomy().get("tensions", {})


def list_frameworks() -> list[str]:
    """Return the flat catalog list of compliance framework identifiers."""
    return list(
        load_taxonomy().get("compliance_frameworks", {}).get("catalog", [])
    )


def get_pillar_tags(pillar_code: str) -> dict:
    """Return the taxonomy metadata for a single pillar.

    Args:
        pillar_code: Pillar identifier, e.g. ``"P1"`` (case-insensitive).

    Returns:
        The pillar's metadata dict (``name``, ``count``, ``primary_vector``,
        ``secondary``), or an empty dict if the pillar is unknown.
    """
    pillars = load_taxonomy().get("pillars", {})
    if pillar_code in pillars:
        return pillars[pillar_code]
    # Be lenient about casing (e.g. "p1" -> "P1").
    return pillars.get(str(pillar_code).upper(), {})

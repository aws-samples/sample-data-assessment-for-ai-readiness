"""FORGE Delta Engine — delta computation and classification.

Compares two most recent assessment records to produce score deltas,
per-pillar deltas with classification, and band transitions.

Supports both single-platform (legacy) and multi-platform (estate) deltas.
"""

from pathlib import Path
from typing import Optional

from forge.delta_engine import BandTransition, DeltaResult, EstateDeltaResult, PillarDelta, PlatformDelta
from forge.delta_engine.reader import read_history


# Band ordering from lowest to highest tier
BAND_ORDER: list[str] = [
    "UNREADY",
    "FOUNDATIONAL",
    "GOVERNED",
    "AGENT-READY",
    "FORGE-NATIVE",
]

# All 9 pillars in canonical order
PILLARS: list[str] = ["P1", "P2", "P3", "P4", "P5", "P6", "P7", "P8", "P9"]


def _classify_delta(delta: float) -> str:
    """Classify a delta value as improvement, regression, or unchanged."""
    if delta > 0:
        return "improvement"
    elif delta < 0:
        return "regression"
    else:
        return "unchanged"


def _detect_band_transition(
    previous_band: str, current_band: str
) -> Optional[BandTransition]:
    """Detect a band transition and classify its direction.

    Returns None if bands are the same. Returns BandTransition with
    direction 'upgrade' if the new band is higher tier, 'downgrade' if lower.
    """
    if previous_band == current_band:
        return None

    previous_rank = BAND_ORDER.index(previous_band)
    current_rank = BAND_ORDER.index(current_band)

    direction = "upgrade" if current_rank > previous_rank else "downgrade"
    return BandTransition(
        previous_band=previous_band,
        current_band=current_band,
        direction=direction,
    )


def compute_delta(history_path: Path = Path("forge_output/forge_history.jsonl")) -> DeltaResult:
    """Compute delta between the two most recent assessment records.

    Algorithm:
        1. Read history using reader.read_history(path)
        2. If fewer than 2 records: return DeltaResult(available=False)
        3. Take the last two records (previous, current)
        4. Compute score_delta = round(current forge_score - previous forge_score, 1)
        5. For each pillar P1-P9: compute per-pillar delta, classify
        6. Detect band transitions (upgrade/downgrade)

    Args:
        history_path: Path to the JSONL history file.

    Returns:
        DeltaResult with available=False if fewer than 2 records exist.
    """
    records = read_history(history_path)

    if len(records) < 2:
        return DeltaResult(
            available=False,
            score_delta=0.0,
            pillar_deltas=[],
            band_transition=None,
            improved_count=0,
            regressed_count=0,
        )

    previous = records[-2]
    current = records[-1]

    # Compute overall score delta
    score_delta = round(current["forge_score"] - previous["forge_score"], 1)

    # Compute per-pillar deltas
    pillar_deltas: list[PillarDelta] = []
    improved_count = 0
    regressed_count = 0

    previous_pillars = previous.get("pillar_scores", {})
    current_pillars = current.get("pillar_scores", {})

    for pillar in PILLARS:
        prev_score = previous_pillars.get(pillar, 0.0)
        curr_score = current_pillars.get(pillar, 0.0)
        delta = round(curr_score - prev_score, 1)
        classification = _classify_delta(delta)

        if classification == "improvement":
            improved_count += 1
        elif classification == "regression":
            regressed_count += 1

        pillar_deltas.append(
            PillarDelta(
                pillar=pillar,
                previous=prev_score,
                current=curr_score,
                delta=delta,
                classification=classification,
            )
        )

    # Detect band transition
    previous_band = previous.get("score_band", "")
    current_band = current.get("score_band", "")
    band_transition = _detect_band_transition(previous_band, current_band)

    return DeltaResult(
        available=True,
        score_delta=score_delta,
        pillar_deltas=pillar_deltas,
        band_transition=band_transition,
        improved_count=improved_count,
        regressed_count=regressed_count,
    )


def _classify_platform_delta(delta: Optional[float]) -> str:
    """Classify a platform delta as improved, regressed, unchanged, or newly_assessed."""
    if delta is None:
        return "newly_assessed"
    if delta > 0:
        return "improved"
    elif delta < 0:
        return "regressed"
    else:
        return "unchanged"


def compute_estate_delta(
    history_path: Path = Path("forge_output/forge_history.jsonl"),
) -> EstateDeltaResult:
    """Compute delta between two most recent estate assessments.

    Handles:
      - Estate-level score delta (uses estate_score field, falls back to forge_score)
      - Per-platform score deltas (when both assessments have that platform)
      - New platform appearing: reports as "newly_assessed" (no delta computed)
      - Pillar deltas (from merged pillar scores)

    Algorithm:
        1. Read history, find the two most recent records
        2. If < 2 records: return EstateDeltaResult(available=False, ...)
        3. Compute estate score delta:
           - Look for "estate_score" field first (multi-platform)
           - Fall back to "forge_score" (single-platform backward compat)
        4. Compute platform deltas:
           - Get current.platform_scores and previous.platform_scores
           - For platforms in both: compute delta, classify
           - For platforms only in current: status="newly_assessed", delta=None
        5. Compute pillar deltas (same as existing compute_delta but use estate merged pillars)
        6. Detect band transitions (use estate_band or score_band)

    Args:
        history_path: Path to the JSONL history file.

    Returns:
        EstateDeltaResult with available=False if fewer than 2 records exist.
    """
    records = read_history(history_path)

    if len(records) < 2:
        return EstateDeltaResult(
            available=False,
            estate_score_delta=0.0,
            estate_band_transition=None,
            platform_deltas=[],
            pillar_deltas=[],
            improved_count=0,
            regressed_count=0,
            new_platforms=[],
        )

    previous = records[-2]
    current = records[-1]

    # Compute estate score delta — prefer estate_score, fall back to forge_score
    prev_estate_score = previous.get("estate_score", previous.get("forge_score", 0.0))
    curr_estate_score = current.get("estate_score", current.get("forge_score", 0.0))
    estate_score_delta = round(curr_estate_score - prev_estate_score, 1)

    # Compute platform deltas
    prev_platform_scores: dict = previous.get("platform_scores", {})
    curr_platform_scores: dict = current.get("platform_scores", {})

    platform_deltas: list[PlatformDelta] = []
    new_platforms: list[str] = []

    # All platforms in the current assessment
    all_current_platforms = set(curr_platform_scores.keys())
    all_previous_platforms = set(prev_platform_scores.keys())

    for platform in sorted(all_current_platforms):
        curr_score = curr_platform_scores[platform]
        if platform in all_previous_platforms:
            # Platform exists in both — compute delta
            prev_score = prev_platform_scores[platform]
            delta = round(curr_score - prev_score, 1)
            status = _classify_platform_delta(delta)
            platform_deltas.append(
                PlatformDelta(
                    platform=platform,
                    previous_score=prev_score,
                    current_score=curr_score,
                    delta=delta,
                    status=status,
                )
            )
        else:
            # New platform — report as newly assessed
            new_platforms.append(platform)
            platform_deltas.append(
                PlatformDelta(
                    platform=platform,
                    previous_score=None,
                    current_score=curr_score,
                    delta=None,
                    status="newly_assessed",
                )
            )

    # Compute per-pillar deltas (using estate-level merged pillar scores)
    pillar_deltas: list[PillarDelta] = []
    improved_count = 0
    regressed_count = 0

    previous_pillars = previous.get("pillar_scores", {})
    current_pillars = current.get("pillar_scores", {})

    for pillar in PILLARS:
        prev_score = previous_pillars.get(pillar, 0.0)
        curr_score = current_pillars.get(pillar, 0.0)
        delta = round(curr_score - prev_score, 1)
        classification = _classify_delta(delta)

        if classification == "improvement":
            improved_count += 1
        elif classification == "regression":
            regressed_count += 1

        pillar_deltas.append(
            PillarDelta(
                pillar=pillar,
                previous=prev_score,
                current=curr_score,
                delta=delta,
                classification=classification,
            )
        )

    # Detect band transition — prefer estate_band, fall back to score_band
    previous_band = previous.get("estate_band", previous.get("score_band", ""))
    current_band = current.get("estate_band", current.get("score_band", ""))
    estate_band_transition = _detect_band_transition(previous_band, current_band)

    return EstateDeltaResult(
        available=True,
        estate_score_delta=estate_score_delta,
        estate_band_transition=estate_band_transition,
        platform_deltas=platform_deltas,
        pillar_deltas=pillar_deltas,
        improved_count=improved_count,
        regressed_count=regressed_count,
        new_platforms=new_platforms,
    )

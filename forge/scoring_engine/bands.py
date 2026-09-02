"""
FORGE 2.3 — Readiness Band Classification

Maps a FORGE score (0–100) to one of five maturity bands using decimal boundaries.
"""
from forge.models import ReadinessBand


def classify_band(forge_score: float) -> ReadinessBand:
    """Classify a FORGE score into a readiness band.

    Band boundaries (decimal thresholds):
        UNREADY:       score < 26.0
        FOUNDATIONAL:  26.0 ≤ score < 51.0
        GOVERNED:      51.0 ≤ score < 76.0
        AGENT-READY:   76.0 ≤ score < 91.0
        FORGE-NATIVE:  score ≥ 91.0

    Args:
        forge_score: The computed FORGE score (0.0–100.0)

    Returns:
        The corresponding ReadinessBand enum value

    Raises:
        ValueError: If forge_score is outside the valid range [0.0, 100.0]
    """
    if forge_score < 0.0 or forge_score > 100.0:
        raise ValueError(
            f"FORGE score {forge_score} is outside the valid range of 0.0 to 100.0"
        )

    if forge_score >= 91.0:
        return ReadinessBand.FORGE_NATIVE
    elif forge_score >= 76.0:
        return ReadinessBand.AGENT_READY
    elif forge_score >= 51.0:
        return ReadinessBand.GOVERNED
    elif forge_score >= 26.0:
        return ReadinessBand.FOUNDATIONAL
    else:
        return ReadinessBand.UNREADY

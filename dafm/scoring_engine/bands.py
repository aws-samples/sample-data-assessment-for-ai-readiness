"""
DAFM — Readiness Band Classification

Maps a DAFM score (0–100) to one of five maturity bands using decimal boundaries.
"""
from dafm.models import ReadinessBand


def classify_band(dafm_score: float) -> ReadinessBand:
    """Classify a DAFM score into a readiness band.

    Band boundaries (decimal thresholds):
        UNREADY:       score < 26.0
        FOUNDATIONAL:  26.0 ≤ score < 51.0
        GOVERNED:      51.0 ≤ score < 76.0
        AGENT-READY:   76.0 ≤ score < 91.0
        DAFM-NATIVE:  score ≥ 91.0

    Args:
        dafm_score: The computed DAFM score (0.0–100.0)

    Returns:
        The corresponding ReadinessBand enum value

    Raises:
        ValueError: If dafm_score is outside the valid range [0.0, 100.0]
    """
    if dafm_score < 0.0 or dafm_score > 100.0:
        raise ValueError(
            f"DAFM score {dafm_score} is outside the valid range of 0.0 to 100.0"
        )

    if dafm_score >= 91.0:
        return ReadinessBand.DAFM_NATIVE
    elif dafm_score >= 76.0:
        return ReadinessBand.AGENT_READY
    elif dafm_score >= 51.0:
        return ReadinessBand.GOVERNED
    elif dafm_score >= 26.0:
        return ReadinessBand.FOUNDATIONAL
    else:
        return ReadinessBand.UNREADY

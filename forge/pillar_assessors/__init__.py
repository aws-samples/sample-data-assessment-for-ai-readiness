"""
FORGE 2.3 — Pillar Assessors Package

Deep assessment logic for all 9 FORGE pillars (142 criteria).
Each pillar's assessment is in its own module (p1.py through p9.py).
"""
import logging

from forge.pillar_assessors.p1 import assess_p1
from forge.pillar_assessors.p2 import assess_p2
from forge.pillar_assessors.p3 import assess_p3
from forge.pillar_assessors.p4 import assess_p4
from forge.pillar_assessors.p5 import assess_p5
from forge.pillar_assessors.p6 import assess_p6
from forge.pillar_assessors.p7 import assess_p7
from forge.pillar_assessors.p8 import assess_p8
from forge.pillar_assessors.p9 import assess_p9

logger = logging.getLogger(__name__)

__all__ = [
    "assess_p1",
    "assess_p2",
    "assess_p3",
    "assess_p4",
    "assess_p5",
    "assess_p6",
    "assess_p7",
    "assess_p8",
    "assess_p9",
    "run_pillar_assessors",
]

ASSESSORS = {
    "P1": assess_p1,
    "P2": assess_p2,
    "P3": assess_p3,
    "P4": assess_p4,
    "P5": assess_p5,
    "P6": assess_p6,
    "P7": assess_p7,
    "P8": assess_p8,
    "P9": assess_p9,
}


def run_pillar_assessors(region: str, profile_name: str = None) -> dict:
    """Run all 9 pillar assessors and return their raw results.

    If profile_name is provided, set up a boto3 session with that profile
    before running assessors.

    Returns:
        Dict mapping pillar code (e.g. "P1") to the assessor result dict
        containing 'criteria' list with 'met' and 'evidence' per criterion.
    """
    if profile_name:
        import boto3
        boto3.setup_default_session(profile_name=profile_name)

    results = {}
    for code, assessor_fn in ASSESSORS.items():
        try:
            result = assessor_fn(region)
            results[code] = result
        except Exception as e:
            logger.warning("Assessor %s failed: %s", code, e)
            results[code] = {"code": code, "criteria": []}

    return results

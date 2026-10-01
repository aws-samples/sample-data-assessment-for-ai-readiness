"""
FORGE — Total Cost of Ownership (TCO) Indicator

Computes a 1–5 TCO indicator for a criterion (or an aggregated pillar) from
three grounded inputs defined in ``forge_config/tag_taxonomy.yaml`` (v0.2):

* ``cost``                 — spend to acquire/run the capability
                              ("low" | "medium" | "high").
* ``operational_overhead`` — ongoing operational burden to keep it healthy
                              ("low" | "medium" | "high").
* ``severity``             — a multiplier reflecting how consequential the
                              capability is ("low" | "medium" | "high").

Grounding
---------
The base is the sum of the cost and operational-overhead points (each
low/medium/high -> 1/2/3), giving a 2..6 range. The severity multiplier
(0.8 / 1.0 / 1.3) scales that base, and the result is linearly mapped onto the
1..5 indicator scale and clamped. An all-"low" criterion lands at 1; an
all-"high" criterion lands at 5. A criterion with no cost/overhead signal is
treated as unscored and returns 0.

The constants and formula below mirror ``tco_indicator`` in the taxonomy YAML
exactly:

    tco = clamp(round(1 + ((cost_pts + overhead_pts) * severity_mult - 1.6)
                      * (4/6.2)), 1, 5)
"""
from __future__ import annotations

COST_PTS = {"low": 1, "medium": 2, "high": 3}
SEV_MULT = {"low": 0.8, "medium": 1.0, "high": 1.3}


def compute_tco(cost: str, operational_overhead: str, severity: str) -> int:
    """Compute the 1–5 TCO indicator from grounded inputs.

    Args:
        cost: "low" | "medium" | "high" (anything else scores 0 points).
        operational_overhead: "low" | "medium" | "high".
        severity: "low" | "medium" | "high" (anything else -> 1.0 multiplier).

    Returns:
        An integer 1–5 TCO indicator, or 0 when the criterion is unscored
        (no cost and no operational-overhead signal).
    """
    base = COST_PTS.get(cost, 0) + COST_PTS.get(operational_overhead, 0)
    if base == 0:
        return 0  # unscored
    raw = base * SEV_MULT.get(severity, 1.0)
    return max(1, min(5, round(1 + (raw - 1.6) * (4 / 6.2))))

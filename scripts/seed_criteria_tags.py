#!/usr/bin/env python3
"""Seed tool only. Generates a first-draft tag file from keyword rules over criterion names, for human review. The reviewed source of truth is dafm_config/criteria_tags.yaml; this script never writes to it. Use it to seed tags for newly added criteria, then copy reviewed entries into criteria_tags.yaml by hand."""
from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dafm.criteria_registry import CRITERIA_REGISTRY  # noqa: E402

TAXONOMY_PATH = ROOT / "dafm_config" / "tag_taxonomy.yaml"
OUTPUT_PATH = ROOT / "dafm_config" / "criteria_tags.seed.yaml"
PROTECTED_PATH = ROOT / "dafm_config" / "criteria_tags.yaml"

MAX_VECTORS = 3

PILLAR_DEFAULT_TENSION = {
    "P1": "portable_vs_maturity",
    "P2": "coverage_vs_precision",
    "P3": "trust_vs_velocity",
    "P4": "trust_vs_velocity",
    "P5": "centralization_vs_federation",
    "P6": "centralization_vs_federation",
    "P7": "freshness_vs_cost",
    "P8": "autonomy_vs_safety",
    "P9": "autonomy_vs_safety",
}

# Rules are evaluated in this order. The tension comes from the first match.
# "severity_high_keywords": if set, severity is bumped to high only when one of
# these keywords matches; otherwise a match of the rule bumps severity to high
# when "severity" is "high".
RULES = [
    {
        "keywords": ["access", "permission", "grant", "tenant", "identity", "auth",
                     "row", "column", "tag-based", "rbac", "abac"],
        "vectors": ["fine_grained_access_control", "governance"],
        "tension": "centralization_vs_federation",
        "compliance": ["HIPAA", "FINRA", "SOC2", "GDPR"],
        "severity": "high",
    },
    {
        "keywords": ["lineage", "provenance", "history", "version", "audit", "trail", "log"],
        "vectors": ["reliable", "governance"],
        "tension": "trust_vs_velocity",
        "compliance": ["SOC2", "ISO_27001", "EU_AI_ACT"],
    },
    {
        "keywords": ["real-time", "realtime", "stream", "zero-etl", "freshness",
                     "latency", "cdc"],
        "vectors": ["current"],
        "tension": "freshness_vs_cost",
    },
    {
        "keywords": ["open table", "iceberg", "delta", "format", "federated",
                     "cross-engine", "multi-engine", "rest api", "mcp", "interoperab"],
        "vectors": ["open_framework", "interoperable"],
        "tension": "portable_vs_maturity",
    },
    {
        "keywords": ["guardrail", "policy", "control", "approval", "explain",
                     "decision", "human-in-the-loop"],
        "vectors": ["controllable"],
        "tension": "autonomy_vs_safety",
        "compliance": ["EU_AI_ACT", "SOC2"],
        "severity": "high",
    },
    {
        "keywords": ["glossary", "semantic", "description", "catalog", "embedding",
                     "retrieval", "vector"],
        "vectors": ["relevance"],
        "tension": "coverage_vs_precision",
    },
    {
        "keywords": ["quality", "contract", "classification", "pii", "sensitive", "masking"],
        "vectors": ["reliable"],
        "tension": "trust_vs_velocity",
        "compliance": ["GDPR", "HIPAA", "CCPA"],
        "severity_high_keywords": ["pii", "sensitive", "masking"],
    },
    {
        "keywords": ["delete", "erasure", "retention", "residency", "region"],
        "vectors": [],
        "tension": None,  # compliance only; does not set the tension
        "compliance": ["GDPR", "CCPA", "DORA"],
    },
]


def _matches(keyword: str, text: str) -> bool:
    return re.search(r"\b" + re.escape(keyword), text) is not None


def _dedupe(items):
    seen, out = set(), []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def build_entry(criterion, pillars: dict) -> dict:
    text = f"{criterion.name} {criterion.description}".lower()
    primary = pillars[criterion.pillar]["primary_vector"]

    vectors = [primary]
    tension = None
    compliance: list[str] = []
    severity = "medium"
    severity_bumped = False
    rule_vectors_added = False

    for rule in RULES:
        hits = [k for k in rule["keywords"] if _matches(k, text)]
        if not hits:
            continue
        if rule["vectors"]:
            rule_vectors_added = True
        vectors.extend(rule["vectors"])
        if tension is None and rule.get("tension"):
            tension = rule["tension"]
        compliance.extend(rule.get("compliance", []))
        if rule.get("severity") == "high":
            severity, severity_bumped = "high", True
        high_kw = rule.get("severity_high_keywords")
        if high_kw and any(k in hits for k in high_kw):
            severity, severity_bumped = "high", True

    review = ["cost", "operational_overhead"]  # no rule sets these
    if not severity_bumped:
        review.append("severity")
    if tension is None:
        tension = PILLAR_DEFAULT_TENSION[criterion.pillar]
        review.append("tension")
    if not rule_vectors_added:
        review.append("vectors")

    return {
        "name": criterion.name,
        "vectors": _dedupe(vectors)[:MAX_VECTORS],
        "tension": tension,
        "cost": "medium",
        "operational_overhead": "medium",
        "severity": severity,
        "compliance": _dedupe(compliance),
        "review": review,
    }


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    out_path = Path(argv[0]).resolve() if argv else OUTPUT_PATH
    if out_path == PROTECTED_PATH.resolve():
        print(f"Refusing to write {PROTECTED_PATH.relative_to(ROOT)}: it is the reviewed "
              "source of truth. Write to a seed file instead.", file=sys.stderr)
        return 1
    taxonomy = yaml.safe_load(TAXONOMY_PATH.read_text())
    pillars = taxonomy["pillars"]

    entries = {}
    for c in sorted(CRITERIA_REGISTRY, key=lambda c: (int(c.pillar[1:]), c.index)):
        entries[f"{c.pillar}.{c.index}"] = build_entry(c, pillars)

    header = (
        "# DRAFT probe-level criteria tags. Generated by scripts/seed_criteria_tags.py.\n"
        "# Seeded from keyword rules and pillar defaults; needs human review.\n"
        "# 'review' lists the fields that are seeded defaults, not rule matches.\n"
    )
    body = yaml.safe_dump(entries, sort_keys=False, default_flow_style=None,
                          width=120, allow_unicode=True)
    out_path.write_text(header + body)
    print(f"Wrote {len(entries)} entries to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

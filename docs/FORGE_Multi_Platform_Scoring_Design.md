# FORGE Multi-Platform Scoring Design

**Version:** 0.1 (Draft)  
**Date:** July 2026  
**Scope:** Extending FORGE to support hybrid environments (AWS + Databricks + future platforms)

---

## Context

The FORGE Assessment Workbench currently operates exclusively against AWS environments using live API discovery. Most customers run hybrid estates — AWS, Databricks, Azure, Snowflake, etc. This document captures the design decisions for:

1. How the Databricks skill gathers information (decided: **Conversational + Document Ingestion**)
2. How the resulting score is calculated and incorporated into the existing FORGE framework

---

## Decision: Skill Input Approach

**Selected: Option B — Conversational + Document Ingestion (Hybrid)**

The skill starts with open-ended questions ("What do you use in Databricks?"), accepts uploaded docs (cost usage summary, architecture diagrams, Unity Catalog exports), parses docs to pre-fill what it can, then asks targeted follow-ups only for gaps.

**Rationale:** Balances usability and rigor. Conversation fills gaps that docs miss; docs provide hard evidence (cost data, config exports) the conversation can't. Adapts to what the customer knows rather than forcing a rigid checklist.

---

## Score Approach Options

### Option 1: Weighted Platform Mix

Customer declares their workload split (e.g., 60% AWS / 40% Databricks). Each platform produces independent pillar scores. Final pillar score = weighted average.

```
P1_final = platform_weight_aws × P1_aws + platform_weight_dbx × P1_dbx
```

| Strengths | Weaknesses |
|-----------|------------|
| One number per pillar — simple for exec reporting | Customer must declare the split (what does "60% AWS" mean — spend? volume? workload count?) |
| Customer controls the weight, reflects their reality | A platform with zero coverage drags the score even if the other fully covers it |
| Minimal change to existing scoring formula | Hides platform-specific gaps behind an average (75/45 blend = 63, looks "fine" but the 45 is real risk) |
| Easy to explain | Scoring N/A pillars as 0 drags the average unfairly |

---

### Option 2: Criteria Ownership (Disjoint Split)

Each criterion belongs to exactly one platform. No overlap. The existing formula runs on the expanded criteria set as if it were one environment.

| Strengths | Weaknesses |
|-----------|------------|
| Zero formula changes — scoring engine doesn't know platforms exist | Rigid: what if both platforms provide access control? Must pick one |
| No weighting ambiguity — each criterion scored once | Doesn't scale — adding Azure means re-splitting all criteria |
| Clean "who owns this gap?" story for remediation | Doesn't reflect reality where the same concern spans platforms |
| Simplest to implement: tag each criterion with a platform | Customer 95% on AWS gets penalized equally for unmet Databricks criteria |

---

### Option 3: Additive Coverage (Best-of per Criterion)

Both platforms can score a criterion. Take the higher score.

```
criterion_score = max(aws_score, dbx_score)
```

| Strengths | Weaknesses |
|-----------|------------|
| Never penalizes for having more platforms | Dangerously optimistic — hides real risk in hybrid environments |
| Rewards any coverage regardless of where it lives | No incentive to fix gaps on the weaker platform |
| Simple merge logic | Customers can game it: "we have DQ on AWS so our Databricks DQ gap doesn't matter" |
| | Defeats the purpose of multi-platform assessment |

---

### Option 4: Platform Segment Overlay (Separate Scores, Unified View)

Each platform gets a full FORGE score independently. Dashboard shows: AWS Score, Databricks Score, and a combined Estate Score.

| Strengths | Weaknesses |
|-----------|------------|
| Maximum transparency — immediately clear where each platform stands | More visual complexity (multiple scores, radars, bars) |
| Per-platform trend tracking over time | Customer sees uncomfortable gaps (though that's the point) |
| Combined score still available for exec summary | Still need to decide how "combined" works internally |
| Naturally extends to N platforms without re-architecting | Pillars that don't apply to a platform need graceful N/A handling |
| Platform-specific roadmaps fall out naturally | |
| Doesn't hide gaps behind averaging | |

---

### Option 5: Relevant-Criteria-Only (Dynamic Scope)

Pool all criteria from all platforms. Only score criteria relevant to the customer's actual environment. Denominator = total relevant criteria across all platforms.

| Strengths | Weaknesses |
|-----------|------------|
| Fairest — measured only on what you actually use | Fewer criteria → potentially inflated scores |
| Consistent with existing relevance engine (NOT_APPLICABLE already works this way) | Hard to benchmark across customers with different scope sizes |
| No arbitrary splits or weights needed | Customer using very few services looks great (tiny denominator) |
| Scales cleanly: add platform, add criteria, relevance engine handles the rest | Doesn't give platform-level visibility without additional breakdown |
| | "What's relevant" depends on skill conversation quality |

---

## Ranking

| Rank | Option | Rationale |
|------|--------|-----------|
| **1** | **4 — Segment Overlay** | The whole point of assessing Databricks separately is to surface platform-specific gaps. Hiding them behind a blend defeats the purpose. Gives per-platform clarity AND a combined number. Only option that naturally extends to 3+ platforms without redesign. |
| **2** | **5 — Relevant-Criteria-Only** | Most architecturally consistent with existing relevance engine. Pairs well with Option 4 as the scoring mechanism *inside* each segment. |
| **3** | **1 — Weighted Platform Mix** | Good for shipping fast without dashboard complexity. Simple, explainable. But hides gaps and requires customer to declare a number that's hard to define. |
| **4** | **2 — Criteria Ownership** | Clean for two-platform world but brittle at three. Fine if criteria split won't change. |
| **5** | **3 — Additive Coverage** | Too optimistic. Actively misleads about risk posture. Only useful as a "ceiling" exploratory view, not primary score. |

---

## Recommended Approach: Option 4 + Option 5 Combined

Each platform segment uses **relevant-criteria-only** scoring internally (Databricks is only measured on Databricks-relevant criteria). The dashboard shows each platform's score independently. A combined **estate score** uses platform-mix weighting for a single executive number.

```
Per-platform score:
  DBX_FORGE_Score = standard FORGE formula applied to Databricks-relevant criteria only

Combined estate score:
  Estate_Score = Σ(platform_weight × platform_forge_score)
```

### What this gives you:

- **Per-platform visibility** — the actionable signal customers use for remediation
- **Fair scoring within each platform** — not penalized for irrelevant criteria
- **A single combined number** — for the exec slide deck
- **Clean extensibility** — Azure/Snowflake plug in as new segments without re-architecting
- **Per-platform trend tracking** — "Databricks improved from 42 → 58 this quarter"
- **Platform-specific roadmaps** — Databricks remediations point to Unity Catalog, DLT, etc.

### Dashboard implications:

- Top-level gauge shows Estate Score (combined)
- Radar chart gets a toggle: Combined | AWS | Databricks
- New section: Platform Contribution Breakdown (stacked bars per pillar)
- Criteria drill-down gets platform badges (AWS / Databricks / Both)
- Remediation roadmap splits by platform naturally

---

## Next Steps

1. Define the Databricks criteria registry (which of the 142 criteria map, which are new)
2. Design the platform segment data model extension
3. Build the merge/combine logic
4. Extend the dashboard generator for multi-platform views
5. Build the conversational + document-ingestion skill flow

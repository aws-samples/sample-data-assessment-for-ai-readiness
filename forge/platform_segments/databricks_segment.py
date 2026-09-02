"""
FORGE 2.4 — Databricks Platform Segment Producer

Converts the output of the Databricks conversational skill into a complete
PlatformSegment. This module:
  1. Filters the Databricks criteria registry by services the customer uses
  2. Maps scored criteria → CriterionSegmentResult
  3. Marks unused-service criteria as NOT_APPLICABLE
  4. Computes per-pillar scores and applies the FORGE formula for a platform score
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

from forge.models import (
    AnalogDetail,
    CriterionSegmentResult,
    CriterionType,
    PillarScore,
    PlatformSegment,
    RelevanceStatus,
)
from forge.platform_segments.databricks_registry import (
    DATABRICKS_CRITERIA_REGISTRY,
    DATABRICKS_PILLAR_NAMES,
)
from forge.profile_engine import ForgeProfile, resolve_profile
from forge.scoring_engine.bands import classify_band
from forge.scoring_engine.formula import (
    compute_coverage_multiplier,
    compute_forge_score,
    compute_raw_score,
)


# ---------------------------------------------------------------------------
# Skill Conversation State — tracks the Databricks skill's progress
# ---------------------------------------------------------------------------


@dataclass
class SkillConversationState:
    """Tracks the Databricks skill's conversation progress.

    Populated incrementally as documents are parsed and follow-up questions
    are answered. Used by build_databricks_segment() to produce the final
    PlatformSegment.
    """

    services_identified: list[str] = field(default_factory=list)
    """Which Databricks services the customer uses (e.g. ['unity_catalog', 'delta_live_tables'])."""

    documents_uploaded: list[str] = field(default_factory=list)
    """File paths of uploaded documents."""

    document_findings: list = field(default_factory=list)
    """DocumentEvidence objects extracted from uploaded documents."""

    criteria_scored: dict[str, float] = field(default_factory=dict)
    """Criterion key → score mapping (e.g. 'P1.1' → 1.0)."""

    criteria_evidence: dict[str, str] = field(default_factory=dict)
    """Criterion key → evidence text (e.g. 'P1.1' → 'UC API confirmed active')."""

    criteria_confidence: dict[str, float] = field(default_factory=dict)
    """Criterion key → confidence score (e.g. 'P1.1' → 0.85)."""

    analog_details: dict[str, AnalogDetail] = field(default_factory=dict)
    """Criterion key → AnalogDetail for analog criteria (e.g. 'P4.2' → AnalogDetail(...))."""

    pending_questions: list[dict] = field(default_factory=list)
    """Questions not yet asked to the user."""

    phase: str = "document_upload"
    """Current phase: 'document_upload' | 'document_review' | 'follow_up' | 'complete'."""

    # ─── Persistence ───────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        """Serialize state to a JSON-compatible dict for persistence."""
        analog_details_serialized = {
            k: {"numerator": v.numerator, "denominator": v.denominator, "platform": v.platform}
            for k, v in self.analog_details.items()
        }
        return {
            "services_identified": self.services_identified,
            "documents_uploaded": self.documents_uploaded,
            "criteria_scored": self.criteria_scored,
            "criteria_evidence": self.criteria_evidence,
            "criteria_confidence": self.criteria_confidence,
            "analog_details": analog_details_serialized,
            "phase": self.phase,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SkillConversationState":
        """Deserialize state from a JSON dict."""
        analog_details = {
            k: AnalogDetail(
                numerator=v["numerator"],
                denominator=v["denominator"],
                platform=v["platform"],
            )
            for k, v in data.get("analog_details", {}).items()
        }
        return cls(
            services_identified=data.get("services_identified", []),
            documents_uploaded=data.get("documents_uploaded", []),
            document_findings=[],  # Not persisted (non-serializable placeholders)
            criteria_scored=data.get("criteria_scored", {}),
            criteria_evidence=data.get("criteria_evidence", {}),
            criteria_confidence=data.get("criteria_confidence", {}),
            analog_details=analog_details,
            pending_questions=[],  # Not persisted (ephemeral)
            phase=data.get("phase", "complete"),
        )

    def save(self, path: Optional["Path"] = None) -> "Path":
        """Persist state to JSON. Default: forge_output/databricks_skill_state.json"""
        import json
        from pathlib import Path as _Path

        if path is None:
            path = _Path("forge_output") / "databricks_skill_state.json"
        else:
            path = _Path(path)

        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)
        return path

    @classmethod
    def load(cls, path: Optional["Path"] = None) -> "SkillConversationState":
        """Load state from JSON. Default: forge_output/databricks_skill_state.json

        Raises FileNotFoundError if no saved state exists.
        """
        import json
        from pathlib import Path as _Path

        if path is None:
            path = _Path("forge_output") / "databricks_skill_state.json"
        else:
            path = _Path(path)

        with open(path) as f:
            data = json.load(f)
        return cls.from_dict(data)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_databricks_segment(
    state: SkillConversationState,
    profile: ForgeProfile,
) -> PlatformSegment:
    """Produce a complete Databricks PlatformSegment from the conversation state.

    Algorithm:
      1. Resolve the profile to get effective weights/floors.
      2. Walk every criterion in DATABRICKS_CRITERIA_REGISTRY.
         - If the criterion's services do NOT intersect with state.services_identified
           → mark NOT_APPLICABLE.
         - If intersecting AND criterion_key is in state.criteria_scored
           → use that score + evidence + confidence.
         - If intersecting but NOT scored → mark UNDETERMINED with score=0.0.
      3. Build per-pillar scores from the criterion results.
      4. Apply FORGE formula for platform-level score (using effective weights/floors).
      5. Return PlatformSegment with all results.

    Args:
        state: The skill conversation state with all scored criteria.
        profile: The declared FORGE profile for weight/floor resolution.

    Returns:
        A fully-populated PlatformSegment for Databricks.
    """
    resolved = resolve_profile(profile)
    effective_weights = resolved.effective_weights
    effective_floors = resolved.effective_floors

    # Step 1: Build criterion segment results from registry + state
    criteria_results = _build_criterion_results(state)

    # Step 2: Compute per-pillar scores
    pillar_scores = _build_pillar_scores(criteria_results)

    # Step 3: Apply FORGE formula
    # Only include pillars that have relevant criteria in the score map
    pillar_score_map: dict[str, float] = {}
    for ps in pillar_scores:
        if ps.relevant_count > 0:
            pillar_score_map[ps.code] = ps.raw_score

    raw_score = compute_raw_score(pillar_score_map, effective_weights)
    coverage_multiplier = compute_coverage_multiplier(pillar_score_map, effective_floors)
    forge_score = compute_forge_score(raw_score, coverage_multiplier)
    band = classify_band(forge_score)

    # Step 4: Build summary and metadata
    summary = {
        "forge_score": forge_score,
        "readiness_band": band.value,
        "raw_score": round(raw_score, 2),
        "coverage_multiplier": round(coverage_multiplier, 4),
    }

    metadata = {
        "platform": "databricks",
        "services_identified": list(state.services_identified),
        "documents_uploaded": list(state.documents_uploaded),
        "criteria_scored_count": len(state.criteria_scored),
        "phase_completed": state.phase,
    }

    return PlatformSegment(
        platform="databricks",
        source_type="conversational",
        pillars=pillar_scores,
        criteria=criteria_results,
        summary=summary,
        metadata=metadata,
    )


# ---------------------------------------------------------------------------
# Internal Helpers
# ---------------------------------------------------------------------------


def _build_criterion_results(
    state: SkillConversationState,
) -> list[CriterionSegmentResult]:
    """Walk the registry and produce a CriterionSegmentResult per criterion.

    For each criterion:
      - Check if criterion's services intersect with state.services_identified.
      - If NO intersection → NOT_APPLICABLE
      - If YES and scored → use score/evidence/confidence from state
      - If YES but NOT scored → UNDETERMINED (score=0.0)
    """
    services_set = set(state.services_identified)
    results: list[CriterionSegmentResult] = []

    for criterion_def in DATABRICKS_CRITERIA_REGISTRY:
        criterion_key = f"{criterion_def.pillar}.{criterion_def.index}"
        criterion_services = set(criterion_def.services)

        # Determine relevance based on service intersection
        has_service_overlap = bool(criterion_services & services_set)

        if not has_service_overlap:
            # No overlap → NOT_APPLICABLE
            results.append(CriterionSegmentResult(
                pillar=criterion_def.pillar,
                index=criterion_def.index,
                name=criterion_def.name,
                score=0.0,
                relevance_status=RelevanceStatus.NOT_APPLICABLE,
                confidence_score=0.0,
                evidence="Service(s) not identified in customer environment",
                criterion_type=criterion_def.criterion_type,
                platform="databricks",
                analog_detail=None,
                exclusion_reason=(
                    f"Required service(s) {sorted(criterion_services)} "
                    f"not in identified services"
                ),
            ))
        elif criterion_key in state.criteria_scored:
            # Scored from documents or conversation
            score = state.criteria_scored[criterion_key]
            evidence = state.criteria_evidence.get(criterion_key, "Scored via skill")
            confidence = state.criteria_confidence.get(criterion_key, 0.7)

            # For ANALOG criteria, attach analog_detail if available
            analog_detail: Optional[AnalogDetail] = None
            if criterion_def.criterion_type == CriterionType.ANALOG:
                if criterion_key in state.analog_details:
                    analog_detail = state.analog_details[criterion_key]
                else:
                    # Synthesize analog_detail from score if not explicitly provided
                    # Use score as ratio with denominator=100 as a reasonable default
                    analog_detail = AnalogDetail(
                        numerator=round(score * 100),
                        denominator=100,
                        platform="databricks",
                    )

            results.append(CriterionSegmentResult(
                pillar=criterion_def.pillar,
                index=criterion_def.index,
                name=criterion_def.name,
                score=score,
                relevance_status=RelevanceStatus.RELEVANT,
                confidence_score=confidence,
                evidence=evidence,
                criterion_type=criterion_def.criterion_type,
                platform="databricks",
                analog_detail=analog_detail,
                exclusion_reason=None,
            ))
        else:
            # Service is present but criterion not yet scored → UNDETERMINED
            results.append(CriterionSegmentResult(
                pillar=criterion_def.pillar,
                index=criterion_def.index,
                name=criterion_def.name,
                score=0.0,
                relevance_status=RelevanceStatus.UNDETERMINED,
                confidence_score=0.0,
                evidence="Criterion not yet assessed",
                criterion_type=criterion_def.criterion_type,
                platform="databricks",
                analog_detail=None,
                exclusion_reason=None,
            ))

    return results


def _build_pillar_scores(
    criteria: list[CriterionSegmentResult],
) -> list[PillarScore]:
    """Aggregate criterion results into per-pillar scores for Databricks.

    Only includes pillars that have entries in the Databricks registry
    (P1, P3, P4, P5, P6, P7). Pillars where ALL criteria are NOT_APPLICABLE
    get raw_score=0.0 and relevant_count=0, which signals exclusion from the
    FORGE formula (Requirement 1.3).

    Computes raw_score as:
        (sum of relevant criterion scores / relevant_count) * 100
    """
    # Group criteria by pillar
    pillar_criteria: dict[str, list[CriterionSegmentResult]] = defaultdict(list)
    for cr in criteria:
        pillar_criteria[cr.pillar].append(cr)

    pillar_scores: list[PillarScore] = []

    for code in sorted(DATABRICKS_PILLAR_NAMES.keys()):
        pillar_crs = pillar_criteria.get(code, [])

        relevant = [
            cr for cr in pillar_crs
            if cr.relevance_status in (
                RelevanceStatus.RELEVANT, RelevanceStatus.UNDETERMINED
            )
        ]
        not_applicable = [
            cr for cr in pillar_crs
            if cr.relevance_status == RelevanceStatus.NOT_APPLICABLE
        ]
        undetermined = [
            cr for cr in pillar_crs
            if cr.relevance_status == RelevanceStatus.UNDETERMINED
        ]

        relevant_count = len(relevant)
        not_applicable_count = len(not_applicable)
        undetermined_count = len(undetermined)

        # Compute raw score: average of relevant criterion scores × 100
        if relevant_count > 0:
            score_sum = sum(cr.score for cr in relevant)
            raw_score = round((score_sum / relevant_count) * 100, 2)
        else:
            raw_score = 0.0

        pillar_scores.append(PillarScore(
            code=code,
            name=DATABRICKS_PILLAR_NAMES.get(code, code),
            raw_score=raw_score,
            relevant_count=relevant_count,
            not_applicable_count=not_applicable_count,
            undetermined_count=undetermined_count,
            criteria=[],  # CriterionSegmentResult != CriterionResult; leave empty
        ))

    return pillar_scores

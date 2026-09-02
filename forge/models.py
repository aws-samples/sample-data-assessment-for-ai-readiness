"""
FORGE 2.3 Assessment Workbench — Domain Data Models

Core domain objects used across all modules: enums for classification states,
dataclasses for probe results, validation signals, criterion definitions,
scoring outputs, and relevance configuration.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class RelevanceStatus(Enum):
    """Relevance state for a criterion or service within an assessment."""
    RELEVANT = "relevant"
    NOT_APPLICABLE = "not-applicable"
    UNDETERMINED = "undetermined"


class ServiceClassification(Enum):
    """Classification result from the probe phase."""
    PROVISIONED = "provisioned"
    NOT_PROVISIONED = "not_provisioned"
    UNDETERMINED = "undetermined"


class CriterionType(Enum):
    """Scoring type for a criterion: analog (0.0–1.0) or binary (0 or 1)."""
    ANALOG = "analog"
    BINARY = "binary"


class ReadinessBand(Enum):
    """FORGE readiness band classification tiers."""
    UNREADY = "UNREADY"
    FOUNDATIONAL = "FOUNDATIONAL"
    GOVERNED = "GOVERNED"
    AGENT_READY = "AGENT-READY"
    FORGE_NATIVE = "FORGE-NATIVE"


@dataclass
class ProbeResult:
    """Result of probing a single AWS service for resource existence."""
    service_name: str
    classification: ServiceClassification
    resource_count: int = 0
    error_code: Optional[str] = None
    error_message: Optional[str] = None


@dataclass
class ValidationResult:
    """Result of validating a provisioned service against usage signals."""
    service_name: str
    confidence_score: float  # 0.0 - 1.0
    classification: str  # "active", "dormant"
    cost_90d: Optional[float] = None
    trail_event_count: Optional[int] = None
    cost_access_denied: bool = False
    trail_access_denied: bool = False


@dataclass
class CriterionDefinition:
    """Definition of a single FORGE criterion with its type and service dependencies."""
    pillar: str  # "P1" through "P9"
    index: int
    name: str
    criterion_type: CriterionType  # analog or binary
    services: list[str] = field(default_factory=list)
    description: str = ""


@dataclass
class CriterionResult:
    """Scored result for a single criterion within an assessment."""
    pillar: str
    index: int
    name: str
    score: float  # 0.0 - 1.0
    relevance_status: RelevanceStatus
    confidence_score: float
    evidence: str
    criterion_type: CriterionType
    exclusion_reason: Optional[str] = None
    confidence_reduced: bool = False


@dataclass
class PillarScore:
    """Aggregated score for a single FORGE pillar."""
    code: str
    name: str
    raw_score: float  # 0.0 - 100.0
    relevant_count: int
    not_applicable_count: int
    undetermined_count: int
    criteria: list[CriterionResult] = field(default_factory=list)


@dataclass
class ForgeAssessmentResult:
    """Complete FORGE assessment output containing all pillar scores and metadata."""
    metadata: dict
    pillars: list[PillarScore]
    summary: dict

    @classmethod
    def from_dict(cls, data: dict) -> "ForgeAssessmentResult":
        """Deserialize a ForgeAssessmentResult from a JSON-compatible dict.

        Reconstructs nested PillarScore and CriterionResult objects,
        mapping string enum values back to their enum types.

        Args:
            data: Dictionary loaded from a FORGE assessment JSON file.

        Returns:
            A fully reconstructed ForgeAssessmentResult instance.
        """
        pillars = []
        for p_data in data.get("pillars", []):
            criteria = []
            for c_data in p_data.get("criteria", []):
                criteria.append(CriterionResult(
                    pillar=p_data["code"],
                    index=c_data["index"],
                    name=c_data["name"],
                    score=c_data["score"],
                    relevance_status=RelevanceStatus(c_data["relevance_status"]),
                    confidence_score=c_data.get("confidence_score", 0.8),
                    evidence=c_data.get("evidence", ""),
                    criterion_type=CriterionType(c_data["criterion_type"]),
                    exclusion_reason=c_data.get("exclusion_reason"),
                    confidence_reduced=c_data.get("confidence_reduced", False),
                ))
            pillars.append(PillarScore(
                code=p_data["code"],
                name=p_data["name"],
                raw_score=p_data["raw_score"],
                relevant_count=p_data["relevant_count"],
                not_applicable_count=p_data["not_applicable_count"],
                undetermined_count=p_data.get("undetermined_count", 0),
                criteria=criteria,
            ))

        # Build summary from the scoring block if present
        scoring = data.get("scoring", {})
        summary = data.get("summary", {})
        if scoring and not summary:
            summary = {
                "forge_score": scoring.get("forge_score"),
                "readiness_band": scoring.get("score_band", scoring.get("band")),
                "raw_score": scoring.get("raw_score", 0),
                "coverage_multiplier": scoring.get("coverage_multiplier", 1.0),
            }

        return cls(
            metadata=data.get("metadata", {}),
            pillars=pillars,
            summary=summary,
        )


@dataclass
class RelevanceConfig:
    """Pre-computed relevance configuration generated by the Kiro Skill.

    Written to JSON during the interactive skill session and consumed by
    the collector CLI for deterministic, non-interactive scoring.
    """
    services: dict  # service_name -> {"status": str, "confidence": float}
    criteria_relevance: dict  # "P1.1" -> RelevanceStatus value
    generated_at: str  # ISO 8601 timestamp


# ─── Multi-Platform Data Structures ────────────────────────────────────────────


@dataclass
class AnalogDetail:
    """Stores numerator/denominator for analog criteria to enable accurate pooling."""
    numerator: int       # e.g., 80 tables with DQ rules
    denominator: int     # e.g., 100 total tables
    platform: str        # "aws" or "databricks"


@dataclass
class CriterionSegmentResult:
    """Extended criterion result for multi-platform context."""
    pillar: str
    index: int
    name: str
    score: float                      # 0.0–1.0
    relevance_status: RelevanceStatus
    confidence_score: float
    evidence: str
    criterion_type: CriterionType
    platform: str                     # "aws" | "databricks" | "estate"
    analog_detail: Optional[AnalogDetail] = None  # Only for ANALOG criteria
    exclusion_reason: Optional[str] = None


@dataclass
class PlatformSegment:
    """Independent assessment of a single platform."""
    platform: str                    # "aws", "databricks"
    source_type: str                 # "api_discovery" | "conversational" | "document_ingest"
    pillars: list[PillarScore]       # Per-pillar scores (same structure as today)
    criteria: list[CriterionSegmentResult]  # All criterion results for this platform
    summary: dict                    # forge_score, band, raw_score, coverage_multiplier
    metadata: dict                   # Platform-specific context


@dataclass
class EstateAssessmentResult:
    """Combined multi-platform assessment output."""
    segments: list[PlatformSegment]         # One per platform
    merged_pillars: list[PillarScore]       # Estate-level pillar scores
    merged_criteria: list[CriterionSegmentResult]  # Estate-level merged criteria
    estate_score: float                     # Combined FORGE score
    estate_band: ReadinessBand              # Band classification
    estate_raw_score: float
    estate_coverage_multiplier: float
    metadata: dict                          # customer_name, timestamp, profile, platforms

"""
FORGE 2.4 — Databricks Skill Orchestrator

Document-first assessment flow for Databricks platform segments. Orchestrates:
  1. Document upload and parsing (cost CSVs, config exports)
  2. Summarization of extracted findings
  3. Follow-up question generation for gaps not covered by documents
  4. Response interpretation (plain text → score + evidence + confidence)
  5. Skill flow coordination via phase-based state machine

Usage:
    from forge.skill_support.databricks_skill import (
        get_initial_prompt,
        advance_skill_phase,
        parse_uploaded_documents,
        summarize_findings,
        generate_followup_questions,
        score_from_response,
    )
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Optional

from forge.platform_segments.databricks_segment import SkillConversationState
from forge.platform_segments.databricks_registry import (
    DATABRICKS_CRITERIA_REGISTRY,
    DATABRICKS_PILLAR_NAMES,
    DATABRICKS_SERVICES,
)
from forge.skill_support.databricks_questions import DATABRICKS_QUESTION_BANK


# ---------------------------------------------------------------------------
# Document Evidence placeholder (until forge.document_ingest is created)
# ---------------------------------------------------------------------------

try:
    from forge.document_ingest import DocumentEvidence, parse_cost_usage, parse_config_export
except ImportError:
    # document_ingest module not yet available — define local placeholder
    @dataclass
    class DocumentEvidence:  # type: ignore[no-redef]
        """Evidence extracted from an uploaded document (placeholder)."""

        criterion_id: str
        score: Optional[float]
        evidence: str
        confidence: float
        source_file: str

    def parse_cost_usage(file_path: str) -> list:
        """Stub: parse Databricks cost usage CSV/PDF. Returns empty list until implemented."""
        return []

    def parse_config_export(file_path: str) -> list:
        """Stub: parse UC config export or workspace description. Returns empty until implemented."""
        return []


def _safe_parse_cost_usage(file_path: str) -> list:
    """Safely call parse_cost_usage, returning empty list if not yet implemented."""
    try:
        return parse_cost_usage(file_path)
    except NotImplementedError:
        return []


def _safe_parse_config_export(file_path: str) -> list:
    """Safely call parse_config_export, returning empty list if not yet implemented."""
    try:
        return parse_config_export(file_path)
    except NotImplementedError:
        return []


# ---------------------------------------------------------------------------
# Question Bank — targeted follow-up questions keyed by pillar
# ---------------------------------------------------------------------------

QUESTION_BANK: list[dict] = [
    # P1: Agent Access & Discovery
    {
        "criterion_key": "P1.1",
        "pillar": "P1",
        "text": "Is the Unity Catalog REST API accessible for programmatic queries in your environment?",
        "criteria_ids": ["P1.1"],
    },
    {
        "criterion_key": "P1.2",
        "pillar": "P1",
        "text": "Approximately what percentage of your tables are registered in Unity Catalog?",
        "criteria_ids": ["P1.2"],
    },
    {
        "criterion_key": "P1.5",
        "pillar": "P1",
        "text": "Do you use the three-level namespace (catalog/schema/table) actively across workspaces?",
        "criteria_ids": ["P1.5"],
    },
    {
        "criterion_key": "P1.6",
        "pillar": "P1",
        "text": "Are your tables stored in Delta Lake open format?",
        "criteria_ids": ["P1.6"],
    },
    {
        "criterion_key": "P1.9",
        "pillar": "P1",
        "text": "Do you have SQL Warehouse endpoints available for programmatic agent queries?",
        "criteria_ids": ["P1.9"],
    },
    # P3: Data Lineage & Provenance
    {
        "criterion_key": "P3.1",
        "pillar": "P3",
        "text": "Is Unity Catalog lineage tracking enabled in your workspace?",
        "criteria_ids": ["P3.1"],
    },
    {
        "criterion_key": "P3.2",
        "pillar": "P3",
        "text": "Does your environment capture column-level lineage through Unity Catalog?",
        "criteria_ids": ["P3.2"],
    },
    {
        "criterion_key": "P3.3",
        "pillar": "P3",
        "text": "Approximately what percentage of production tables have lineage captured?",
        "criteria_ids": ["P3.3"],
    },
    {
        "criterion_key": "P3.5",
        "pillar": "P3",
        "text": "Is Delta Live Tables pipeline lineage automatically captured end-to-end?",
        "criteria_ids": ["P3.5"],
    },
    # P4: Data Quality, Contracts & Classification
    {
        "criterion_key": "P4.1",
        "pillar": "P4",
        "text": "Do you use DLT expectations (data quality rules) on production pipelines?",
        "criteria_ids": ["P4.1"],
    },
    {
        "criterion_key": "P4.2",
        "pillar": "P4",
        "text": "Approximately what percentage of production tables have DQ rules or monitors configured?",
        "criteria_ids": ["P4.2"],
    },
    {
        "criterion_key": "P4.5",
        "pillar": "P4",
        "text": "Is Delta Lake schema enforcement active to prevent malformed writes?",
        "criteria_ids": ["P4.5"],
    },
    {
        "criterion_key": "P4.7",
        "pillar": "P4",
        "text": "Are sensitive columns tagged with PII/PHI classification in Unity Catalog?",
        "criteria_ids": ["P4.7"],
    },
    # P5: Access Control, Identity & Tenancy
    {
        "criterion_key": "P5.1",
        "pillar": "P5",
        "text": "Is column-level dynamic masking configured in Unity Catalog?",
        "criteria_ids": ["P5.1"],
    },
    {
        "criterion_key": "P5.2",
        "pillar": "P5",
        "text": "Are row filters applied in Unity Catalog for tenant-level data isolation?",
        "criteria_ids": ["P5.2"],
    },
    {
        "criterion_key": "P5.3",
        "pillar": "P5",
        "text": "Do you use the Unity Catalog GRANT/REVOKE permissions model (not legacy ACLs)?",
        "criteria_ids": ["P5.3"],
    },
    {
        "criterion_key": "P5.4",
        "pillar": "P5",
        "text": "Are service principals configured for machine/agent access to Databricks?",
        "criteria_ids": ["P5.4"],
    },
    # P6: Observability & Audit
    {
        "criterion_key": "P6.1",
        "pillar": "P6",
        "text": "Are Databricks system tables (audit logs) enabled and queryable?",
        "criteria_ids": ["P6.1"],
    },
    {
        "criterion_key": "P6.2",
        "pillar": "P6",
        "text": "Are all table reads and writes logged with user identity in the audit system?",
        "criteria_ids": ["P6.2"],
    },
    {
        "criterion_key": "P6.4",
        "pillar": "P6",
        "text": "Is per-workspace or per-cluster cost attribution available via billing tables?",
        "criteria_ids": ["P6.4"],
    },
    {
        "criterion_key": "P6.6",
        "pillar": "P6",
        "text": "Are MLflow experiments tracked with metrics, parameters, and artifacts logged?",
        "criteria_ids": ["P6.6"],
    },
    # P7: Real-Time, Freshness & Zero-ETL
    {
        "criterion_key": "P7.1",
        "pillar": "P7",
        "text": "Do you have streaming tables or DLT streaming pipelines in production?",
        "criteria_ids": ["P7.1"],
    },
    {
        "criterion_key": "P7.2",
        "pillar": "P7",
        "text": "Are Spark Structured Streaming jobs actively processing real-time data?",
        "criteria_ids": ["P7.2"],
    },
    {
        "criterion_key": "P7.4",
        "pillar": "P7",
        "text": "Is Change Data Feed (CDF) enabled on Delta tables for incremental processing?",
        "criteria_ids": ["P7.4"],
    },
    {
        "criterion_key": "P7.9",
        "pillar": "P7",
        "text": "Do you use Auto Loader (cloudFiles) for automatic file ingestion into Delta Lake?",
        "criteria_ids": ["P7.9"],
    },
]


# ---------------------------------------------------------------------------
# Service detection by file extension
# ---------------------------------------------------------------------------

_COST_FILE_EXTENSIONS = {".csv"}
_CONFIG_FILE_EXTENSIONS = {".pdf", ".txt", ".json", ".yaml", ".yml"}


# ---------------------------------------------------------------------------
# Skill Flow Coordinator — manages conversation phases
# ---------------------------------------------------------------------------


def get_initial_prompt() -> str:
    """Return the Phase 1 document upload prompt.

    Returns the standardized prompt asking for documents.
    """
    return (
        "Please upload your Databricks documentation \u2014 most important is the "
        "cost usage summary, but architecture diagrams, Unity Catalog exports, "
        "or workspace descriptions are also helpful."
    )


def advance_skill_phase(
    state: SkillConversationState,
    file_paths: list[str] | None = None,
    user_response: str | None = None,
) -> tuple[SkillConversationState, str]:
    """Advance the skill through its conversation phases.

    Phase transitions:
      document_upload \u2192 document_review (when files uploaded or user says no docs)
      document_review \u2192 follow_up (when user confirms/corrects findings)
      follow_up \u2192 complete (when all questions answered or none remaining)

    Args:
        state: Current conversation state.
        file_paths: New file paths uploaded (for document_upload phase).
        user_response: User's text response (for document_review/follow_up phases).

    Returns:
        Tuple of (updated_state, next_message_to_user).
    """
    if state.phase == "document_upload":
        if file_paths:
            # Parse documents
            services, evidence = parse_uploaded_documents(file_paths)
            state.services_identified = services
            state.documents_uploaded = file_paths
            state.document_findings = evidence

            # Pre-fill criteria from document evidence
            for ev in evidence:
                if ev.score is not None:
                    state.criteria_scored[ev.criterion_id] = ev.score
                    state.criteria_evidence[ev.criterion_id] = ev.evidence
                    state.criteria_confidence[ev.criterion_id] = ev.confidence

            state.phase = "document_review"
            summary = summarize_findings(state)
            return state, (
                "Here's what I found from your documents:\n\n"
                f"{summary}\n\n"
                "Does this look correct? Any corrections?"
            )
        else:
            # No documents — fallback to open-ended prompt
            state.phase = "document_review"
            return state, _generate_fallback_prompt()

    elif state.phase == "document_review":
        # User confirmed or provided corrections
        if not state.services_identified and user_response:
            # Response to the fallback prompt — extract services from text
            state.services_identified = _process_fallback_response(user_response)

        state.phase = "follow_up"
        questions = generate_followup_questions(state)
        state.pending_questions = questions

        if questions:
            first_q = questions[0]
            return state, (
                "A few quick questions about areas I couldn't determine "
                "from the docs...\n\n"
                f"{first_q['text']}"
            )
        else:
            state.phase = "complete"
            return state, (
                "All criteria have been assessed. "
                "Your Databricks platform segment is ready."
            )

    elif state.phase == "follow_up":
        # Process the answer to the current question
        if state.pending_questions and user_response:
            current_q = state.pending_questions.pop(0)
            score, evidence, confidence = score_from_response(current_q, user_response)

            for cid in current_q.get("criteria_ids", []):
                state.criteria_scored[cid] = score
                state.criteria_evidence[cid] = evidence
                state.criteria_confidence[cid] = confidence

        if state.pending_questions:
            next_q = state.pending_questions[0]
            return state, next_q["text"]
        else:
            state.phase = "complete"
            return state, (
                "All follow-up questions complete. "
                "Your Databricks platform segment is ready."
            )

    return state, "Assessment complete."


def _generate_fallback_prompt() -> str:
    """Return the no-document fallback prompt.

    Delegates to the public generate_fallback_prompt() with a friendly preamble.
    """
    return (
        "No problem! Let's proceed without documents.\n\n"
        + generate_fallback_prompt()
    )


def _process_fallback_response(user_response: str) -> list[str]:
    """Extract Databricks service identifiers from a free-text response.

    Delegates to the public process_fallback_response() function.
    """
    return process_fallback_response(user_response)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse_uploaded_documents(
    file_paths: list[str],
) -> tuple[list[str], list[DocumentEvidence]]:
    """Parse all uploaded documents to identify services and extract evidence.

    Routes files by extension:
      - .csv → cost usage parser (identifies active services)
      - .pdf, .txt, .json, .yaml → config/architecture parser (extracts criterion evidence)

    Args:
        file_paths: List of file paths uploaded by the customer.

    Returns:
        Tuple of:
          - services_identified: List of Databricks service keys with non-zero activity
          - evidence: List of DocumentEvidence objects with criterion-level findings
    """
    services_identified: set[str] = set()
    evidence: list[DocumentEvidence] = []

    for file_path in file_paths:
        ext = os.path.splitext(file_path)[1].lower()

        if ext in _COST_FILE_EXTENSIONS:
            # Parse cost usage — primary signal for service existence
            cost_signals = _safe_parse_cost_usage(file_path)
            for signal in cost_signals:
                if hasattr(signal, "active") and signal.active:
                    services_identified.add(signal.service)
                elif hasattr(signal, "service"):
                    # If cost signal exists at all, the service is at least provisioned
                    services_identified.add(signal.service)

        elif ext in _CONFIG_FILE_EXTENSIONS:
            # Parse config/architecture documents
            doc_evidence = _safe_parse_config_export(file_path)
            evidence.extend(doc_evidence)

            # Also infer services from extracted evidence
            for ev in doc_evidence:
                _infer_services_from_evidence(ev, services_identified)

    return sorted(services_identified), evidence


def summarize_findings(state: SkillConversationState) -> str:
    """Generate a human-readable summary of what was determined from documents.

    Presents:
      - Which services were identified as active
      - How many criteria were pre-filled from document evidence
      - How many criteria still need input

    Args:
        state: Current skill conversation state with parsed findings.

    Returns:
        Multi-line summary string suitable for display to the customer.
    """
    # Count total relevant criteria (not N/A)
    services_set = set(state.services_identified)
    total_relevant = 0
    for criterion in DATABRICKS_CRITERIA_REGISTRY:
        criterion_services = set(criterion.services)
        if criterion_services & services_set:
            total_relevant += 1

    scored_count = len(state.criteria_scored)
    remaining_count = max(0, total_relevant - scored_count)

    # Build service display names
    service_display_names = [
        DATABRICKS_SERVICES.get(svc, svc)
        for svc in state.services_identified
    ]

    lines: list[str] = []

    if service_display_names:
        lines.append(f"✓ Active services: {', '.join(sorted(service_display_names))}")
    else:
        lines.append("✗ No services identified from documents")

    if scored_count > 0:
        lines.append(f"✓ Pre-filled {scored_count} criteria from document evidence")
    else:
        lines.append("✗ No criteria could be pre-filled from documents")

    if remaining_count > 0:
        lines.append(f"✗ {remaining_count} criteria still need input")
    else:
        lines.append("✓ All relevant criteria have been scored")

    return "\n".join(lines)


def generate_followup_questions(
    state: SkillConversationState,
    max_per_pillar: int = 3,
) -> list[dict]:
    """Generate targeted follow-up questions ONLY for gaps not covered by documents.

    For each pillar, finds criteria that:
      1. Are relevant (service overlap with identified services)
      2. Have NOT already been scored from documents
    Then selects up to max_per_pillar questions from the question bank.

    Args:
        state: Current skill conversation state.
        max_per_pillar: Maximum number of follow-up questions per pillar.

    Returns:
        List of question dicts, each with keys:
          criterion_key, pillar, text, criteria_ids
    """
    services_set = set(state.services_identified)
    scored_keys = set(state.criteria_scored.keys())

    # Determine which criteria are relevant but unscored
    unscored_relevant: set[str] = set()
    for criterion in DATABRICKS_CRITERIA_REGISTRY:
        criterion_key = f"{criterion.pillar}.{criterion.index}"
        criterion_services = set(criterion.services)

        # Must have service overlap AND not already scored
        if (criterion_services & services_set) and (criterion_key not in scored_keys):
            unscored_relevant.add(criterion_key)

    # Select questions from the bank that target unscored criteria
    questions: list[dict] = []
    pillar_counts: dict[str, int] = {}

    for question in QUESTION_BANK:
        pillar = question["pillar"]
        pillar_count = pillar_counts.get(pillar, 0)

        # Skip if we've hit the per-pillar limit
        if pillar_count >= max_per_pillar:
            continue

        # Check if any of the question's criteria are in the unscored set
        question_criteria = set(question["criteria_ids"])
        if question_criteria & unscored_relevant:
            questions.append(question)
            pillar_counts[pillar] = pillar_count + 1

    return questions


def score_from_response(
    question: dict,
    user_response: str,
) -> tuple[float, str, float]:
    """Interpret a user's plain-text response into score, evidence, and confidence.

    Uses NLP heuristics to classify the response:
      - Clear affirmative → score=1.0, confidence=0.7
      - Clear negative → score=0.0, confidence=0.7
      - Partial/uncertain → score=0.5, confidence=0.5
      - Numeric percentage detected → analog score, confidence=0.7

    Args:
        question: The question dict that was asked (contains criterion_key, text).
        user_response: The customer's plain-text answer.

    Returns:
        Tuple of (score, evidence_string, confidence).
    """
    response_lower = user_response.strip().lower()

    # Try to extract a numeric percentage (for analog criteria)
    percentage = _extract_percentage(response_lower)
    if percentage is not None:
        score = min(1.0, max(0.0, percentage / 100.0))
        evidence = f"User reported ~{percentage}% — '{user_response.strip()}'"
        return (score, evidence, 0.7)

    # Check partial FIRST — hedging/uncertainty takes priority over pure yes/no
    # because partial responses often contain both affirmative and negative words
    if _is_partial(response_lower):
        evidence = f"User partially confirmed — '{user_response.strip()}'"
        return (0.5, evidence, 0.5)

    # Check for clear affirmative signals
    if _is_affirmative(response_lower):
        evidence = f"User confirmed — '{user_response.strip()}'"
        return (1.0, evidence, 0.7)

    # Check for clear negative signals
    if _is_negative(response_lower):
        evidence = f"User denied — '{user_response.strip()}'"
        return (0.0, evidence, 0.7)

    # Default: uncertain / unclear response
    evidence = f"User response unclear — '{user_response.strip()}'"
    return (0.5, evidence, 0.5)


# ---------------------------------------------------------------------------
# No-Document Fallback Path
# ---------------------------------------------------------------------------

# Mapping of keywords/phrases to service keys for response parsing.
# Each entry maps regex patterns (case-insensitive) to the corresponding
# DATABRICKS_SERVICES key.
_SERVICE_DETECTION_PATTERNS: list[tuple[str, str]] = [
    (r"\bunity\s*catalog\b", "unity_catalog"),
    (r"\buc\b", "unity_catalog"),
    (r"\buc\s*lineage\b", "unity_catalog_lineage"),
    (r"\blineage\b", "unity_catalog_lineage"),
    (r"\bdelta\s*live\s*tables?\b", "delta_live_tables"),
    (r"\bdlt\b", "delta_live_tables"),
    (r"\bdelta\s*lake\b", "delta_lake"),
    (r"\bdelta\b", "delta_lake"),
    (r"\bsql\s*warehouse\b", "sql_warehouse"),
    (r"\bdbsql\b", "sql_warehouse"),
    (r"\bmlflow\b", "mlflow"),
    (r"\bml\s*flow\b", "mlflow"),
    (r"\bmodel\s*registry\b", "mlflow"),
    (r"\bworkflows?\b", "databricks_workflows"),
    (r"\bjob\s*orchestrat", "databricks_workflows"),
    (r"\bstructured\s*streaming\b", "structured_streaming"),
    (r"\bspark\s*streaming\b", "structured_streaming"),
    (r"\bstreaming\b", "structured_streaming"),
    (r"\bsystem\s*tables?\b", "system_tables"),
    (r"\baudit\s*log", "system_tables"),
    (r"\bmodel\s*serving\b", "model_serving"),
    (r"\bserving\s*endpoint", "model_serving"),
    (r"\breal[\s-]*time\s*inference\b", "model_serving"),
    (r"\bauto\s*loader\b", "structured_streaming"),
]


def generate_fallback_prompt() -> str:
    """Generate the no-document fallback prompt.

    Used when the customer has no documents to upload. Returns an open-ended
    prompt asking which Databricks services and features their team uses.

    Returns:
        The open-ended prompt text for the no-document fallback path.
    """
    return (
        "What Databricks services and features does your team use? "
        "For example: Unity Catalog, SQL Warehouse, Delta Live Tables, "
        "MLflow, Structured Streaming, etc."
    )


def process_fallback_response(user_response: str) -> list[str]:
    """Process the user's response to the fallback prompt.

    Extracts service identifiers from a plain-text response describing
    which Databricks services they use. Scans for mentions of known
    Databricks services and maps each mention to the corresponding
    DATABRICKS_SERVICES key.

    Args:
        user_response: Free-text answer about services used.

    Returns:
        Sorted list of unique service keys identified from the response.
        Returns empty list if no services could be identified.
    """
    if not user_response or not user_response.strip():
        return []

    response_lower = user_response.lower()
    identified: set[str] = set()

    for pattern, service_key in _SERVICE_DETECTION_PATTERNS:
        if re.search(pattern, response_lower):
            identified.add(service_key)

    return sorted(identified)


def generate_full_question_set(services: list[str]) -> list[dict]:
    """Generate the full question set when no documents are available.

    Since there's no document evidence, ALL criteria for identified services
    need to be assessed via conversation. Uses the DATABRICKS_QUESTION_BANK
    but doesn't suppress any questions — every question whose required services
    overlap with the identified services is included.

    Args:
        services: List of identified service keys.

    Returns:
        List of all applicable questions from the question bank.
        Each question dict contains: id, pillar, text, criteria_ids, services,
        scoring_logic, positive_keywords, negative_keywords.
    """
    if not services:
        # If no services identified, return all questions (assess everything)
        return list(DATABRICKS_QUESTION_BANK)

    services_set = set(services)
    applicable_questions: list[dict] = []

    for question in DATABRICKS_QUESTION_BANK:
        # Include the question if any of its required services are in the
        # identified services list
        question_services = set(question.get("services", []))
        if question_services & services_set:
            applicable_questions.append(question)

    return applicable_questions


# ---------------------------------------------------------------------------
# Internal Helpers
# ---------------------------------------------------------------------------


def _infer_services_from_evidence(
    ev: DocumentEvidence,
    services: set[str],
) -> None:
    """Infer service presence from a DocumentEvidence criterion_id."""
    # Look up which services the criterion requires
    for criterion in DATABRICKS_CRITERIA_REGISTRY:
        criterion_key = f"{criterion.pillar}.{criterion.index}"
        if criterion_key == ev.criterion_id:
            services.update(criterion.services)
            break


_AFFIRMATIVE_PATTERNS = [
    r"\byes\b",
    r"\byep\b",
    r"\byeah\b",
    r"\bcorrect\b",
    r"\bconfirm(ed)?\b",
    r"\benabled?\b",
    r"\bactive\b",
    r"\bconfigured\b",
    r"\bwe do\b",
    r"\bwe use\b",
    r"\bwe have\b",
    r"\babsolutely\b",
    r"\bdefinitely\b",
    r"\ball of them\b",
    r"\beverywhere\b",
    r"\bfully\b",
    r"\bit'?s in place\b",
    r"\bthat'?s in place\b",
    r"\bhave.+in place\b",
]

_NEGATIVE_PATTERNS = [
    r"\bno\b",
    r"\bnot\b",
    r"\bnope\b",
    r"\bnone\b",
    r"\bnever\b",
    r"\bdon'?t\b",
    r"\bdoesn'?t\b",
    r"\bwe don'?t\b",
    r"\bnot yet\b",
    r"\bnot configured\b",
    r"\bnot enabled\b",
    r"\bnot available\b",
    r"\bdisabled\b",
    r"\bnothing\b",
]

_PARTIAL_PATTERNS = [
    r"\bsome\b",
    r"\bpartial(ly)?\b",
    r"\bin progress\b",
    r"\bworking on\b",
    r"\bplanning\b",
    r"\bnot all\b",
    r"\ba few\b",
    r"\bmost(ly)?\b",
    r"\bnot sure\b",
    r"\bmaybe\b",
    r"\bkind of\b",
    r"\bsort of\b",
    r"\blimited\b",
]


def _is_affirmative(text: str) -> bool:
    """Check if the response is clearly affirmative."""
    # If text also contains negative signals, it's not clearly affirmative
    if any(re.search(pat, text) for pat in _NEGATIVE_PATTERNS):
        return False
    if any(re.search(pat, text) for pat in _PARTIAL_PATTERNS):
        return False
    return any(re.search(pat, text) for pat in _AFFIRMATIVE_PATTERNS)


def _is_negative(text: str) -> bool:
    """Check if the response is clearly negative."""
    # If text also contains affirmative signals, it might be partial
    if any(re.search(pat, text) for pat in _AFFIRMATIVE_PATTERNS):
        return False
    return any(re.search(pat, text) for pat in _NEGATIVE_PATTERNS)


def _is_partial(text: str) -> bool:
    """Check if the response indicates partial/uncertain status."""
    return any(re.search(pat, text) for pat in _PARTIAL_PATTERNS)


def _extract_percentage(text: str) -> Optional[float]:
    """Extract a percentage value from text if present.

    Handles patterns like: "about 80%", "~60 percent", "70-80%", "50/100".
    For ranges, returns the midpoint.
    """
    # Pattern: "X-Y%" range → midpoint (check BEFORE single percentage)
    match = re.search(r"(\d+)\s*[-–]\s*(\d+)\s*(?:%|percent)", text)
    if match:
        low = float(match.group(1))
        high = float(match.group(2))
        return (low + high) / 2.0

    # Pattern: "X%" or "X percent"
    match = re.search(r"(\d+(?:\.\d+)?)\s*(?:%|percent)", text)
    if match:
        return float(match.group(1))

    # Pattern: "X/Y" ratio (e.g., "80/100")
    match = re.search(r"(\d+)\s*/\s*(\d+)", text)
    if match:
        num = float(match.group(1))
        den = float(match.group(2))
        if den > 0:
            return (num / den) * 100.0

    return None

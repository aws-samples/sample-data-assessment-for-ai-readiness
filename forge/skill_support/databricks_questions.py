"""
FORGE 2.3 Assessment Workbench — Databricks Follow-Up Question Bank

Defines the structured question bank used by the Databricks Skill during the
follow-up phase of the document-first assessment flow. Questions are only asked
when uploaded documents did not provide sufficient evidence to score linked criteria.

Each question:
- Targets one or more criteria in the Databricks criteria registry
- Specifies which Databricks services must be active for the question to be relevant
- Includes keyword lists for automated response interpretation (analog/binary scoring)
- Is suppressed when all linked criteria have already been scored from document evidence

Usage:
    from forge.skill_support.databricks_questions import (
        DATABRICKS_QUESTION_BANK,
        get_questions_for_pillar,
        get_unanswered_questions,
    )
"""
from __future__ import annotations


# ---------------------------------------------------------------------------
# Question Bank — structured follow-up questions per pillar
# ---------------------------------------------------------------------------

DATABRICKS_QUESTION_BANK: list[dict] = [
    # -----------------------------------------------------------------------
    # P1: Agent Access & Discovery
    # -----------------------------------------------------------------------
    {
        "id": "q_p1_01",
        "pillar": "P1",
        "text": "Are all your data assets registered in Unity Catalog?",
        "criteria_ids": ["P1.1", "P1.2"],
        "services": ["unity_catalog"],
        "scoring_logic": "analog",
        "positive_keywords": ["yes", "all", "registered", "100%", "catalog", "everything", "fully"],
        "negative_keywords": ["no", "not", "some", "few", "haven't", "partial", "legacy", "hive"],
    },
    {
        "id": "q_p1_02",
        "pillar": "P1",
        "text": "Do you use the three-level namespace (catalog.schema.table) consistently?",
        "criteria_ids": ["P1.5"],
        "services": ["unity_catalog"],
        "scoring_logic": "binary",
        "positive_keywords": ["yes", "always", "consistently", "enforced", "standard", "namespace"],
        "negative_keywords": ["no", "not", "sometimes", "mixed", "legacy", "hive_metastore"],
    },
    {
        "id": "q_p1_03",
        "pillar": "P1",
        "text": "Can external tools (e.g., Spark, Trino) access your Delta Lake tables?",
        "criteria_ids": ["P1.6", "P1.8"],
        "services": ["delta_lake", "unity_catalog"],
        "scoring_logic": "binary",
        "positive_keywords": ["yes", "open", "delta", "multi-engine", "external", "trino", "spark", "presto"],
        "negative_keywords": ["no", "not", "locked", "only databricks", "can't", "proprietary"],
    },
    # -----------------------------------------------------------------------
    # P3: Data Lineage & Provenance
    # -----------------------------------------------------------------------
    {
        "id": "q_p3_01",
        "pillar": "P3",
        "text": "Is lineage tracking enabled in your workspace?",
        "criteria_ids": ["P3.1", "P3.2"],
        "services": ["unity_catalog_lineage"],
        "scoring_logic": "binary",
        "positive_keywords": ["yes", "enabled", "active", "tracking", "lineage", "turned on", "configured"],
        "negative_keywords": ["no", "not", "disabled", "haven't", "don't know", "off"],
    },
    {
        "id": "q_p3_02",
        "pillar": "P3",
        "text": "Does Unity Catalog capture column-level lineage automatically?",
        "criteria_ids": ["P3.2", "P3.3"],
        "services": ["unity_catalog_lineage"],
        "scoring_logic": "binary",
        "positive_keywords": ["yes", "column", "automatic", "captured", "granular", "fine-grained"],
        "negative_keywords": ["no", "not", "only table", "table-level", "haven't", "disabled"],
    },
    {
        "id": "q_p3_03",
        "pillar": "P3",
        "text": "Are DLT pipeline lineage and workflow job lineage visible in UC?",
        "criteria_ids": ["P3.5", "P3.7"],
        "services": ["delta_live_tables", "databricks_workflows", "unity_catalog_lineage"],
        "scoring_logic": "binary",
        "positive_keywords": ["yes", "visible", "tracked", "captured", "both", "dlt", "workflow", "jobs"],
        "negative_keywords": ["no", "not", "only dlt", "only workflows", "partial", "missing"],
    },
    # -----------------------------------------------------------------------
    # P4: Data Quality, Contracts & Classification
    # -----------------------------------------------------------------------
    {
        "id": "q_p4_01",
        "pillar": "P4",
        "text": "Do you use DLT expectations or DQ monitors on production tables?",
        "criteria_ids": ["P4.1", "P4.2"],
        "services": ["delta_live_tables"],
        "scoring_logic": "analog",
        "positive_keywords": ["yes", "expectations", "monitors", "all", "production", "dlt", "quality", "rules"],
        "negative_keywords": ["no", "not", "some", "few", "haven't", "planning", "none"],
    },
    {
        "id": "q_p4_02",
        "pillar": "P4",
        "text": "Is schema enforcement enabled on your Delta tables?",
        "criteria_ids": ["P4.5", "P4.6"],
        "services": ["delta_lake"],
        "scoring_logic": "binary",
        "positive_keywords": ["yes", "enforced", "enabled", "strict", "schema", "reject", "validation"],
        "negative_keywords": ["no", "not", "disabled", "merge schema", "auto", "permissive"],
    },
    {
        "id": "q_p4_03",
        "pillar": "P4",
        "text": "Have you tagged sensitive columns (PII/PHI) in Unity Catalog?",
        "criteria_ids": ["P4.7"],
        "services": ["unity_catalog"],
        "scoring_logic": "analog",
        "positive_keywords": ["yes", "tagged", "classified", "pii", "phi", "sensitive", "all", "labels"],
        "negative_keywords": ["no", "not", "some", "haven't", "planning", "few", "none"],
    },
    # -----------------------------------------------------------------------
    # P5: Access Control, Identity & Tenancy
    # -----------------------------------------------------------------------
    {
        "id": "q_p5_01",
        "pillar": "P5",
        "text": "Is column-level masking or row filtering configured in UC?",
        "criteria_ids": ["P5.1", "P5.2"],
        "services": ["unity_catalog"],
        "scoring_logic": "binary",
        "positive_keywords": ["yes", "masking", "filtering", "configured", "row", "column", "dynamic"],
        "negative_keywords": ["no", "not", "haven't", "planning", "disabled", "none"],
    },
    {
        "id": "q_p5_02",
        "pillar": "P5",
        "text": "Do you use service principals for automated/agent access?",
        "criteria_ids": ["P5.4"],
        "services": ["unity_catalog"],
        "scoring_logic": "binary",
        "positive_keywords": ["yes", "service principal", "automated", "machine", "agent", "spn", "identity"],
        "negative_keywords": ["no", "not", "personal tokens", "user accounts", "haven't", "manual"],
    },
    {
        "id": "q_p5_03",
        "pillar": "P5",
        "text": "Are personal access tokens restricted via workspace policies?",
        "criteria_ids": ["P5.6"],
        "services": ["unity_catalog"],
        "scoring_logic": "binary",
        "positive_keywords": ["yes", "restricted", "policies", "managed", "limited", "disabled", "controlled"],
        "negative_keywords": ["no", "not", "unrestricted", "open", "anyone", "haven't", "default"],
    },
    # -----------------------------------------------------------------------
    # P6: Observability & Audit
    # -----------------------------------------------------------------------
    {
        "id": "q_p6_01",
        "pillar": "P6",
        "text": "Are system tables (audit logs) enabled and queried?",
        "criteria_ids": ["P6.1", "P6.2"],
        "services": ["system_tables"],
        "scoring_logic": "binary",
        "positive_keywords": ["yes", "enabled", "queried", "active", "audit", "system tables", "logging"],
        "negative_keywords": ["no", "not", "disabled", "haven't", "don't use", "not enabled"],
    },
    {
        "id": "q_p6_02",
        "pillar": "P6",
        "text": "Can you run SQL queries against audit log data for compliance?",
        "criteria_ids": ["P6.7"],
        "services": ["system_tables", "sql_warehouse"],
        "scoring_logic": "binary",
        "positive_keywords": ["yes", "sql", "query", "compliance", "reports", "warehouse", "queryable"],
        "negative_keywords": ["no", "not", "can't", "export only", "haven't", "no access"],
    },
    {
        "id": "q_p6_03",
        "pillar": "P6",
        "text": "Is per-workspace cost attribution available?",
        "criteria_ids": ["P6.4"],
        "services": ["system_tables"],
        "scoring_logic": "binary",
        "positive_keywords": ["yes", "attribution", "workspace", "billing", "cost", "tracked", "tags"],
        "negative_keywords": ["no", "not", "aggregate", "can't", "haven't", "single bill"],
    },
    # -----------------------------------------------------------------------
    # P7: Real-Time, Freshness & Zero-ETL
    # -----------------------------------------------------------------------
    {
        "id": "q_p7_01",
        "pillar": "P7",
        "text": "Do you have streaming tables or real-time pipelines?",
        "criteria_ids": ["P7.1", "P7.2"],
        "services": ["delta_live_tables", "structured_streaming"],
        "scoring_logic": "binary",
        "positive_keywords": ["yes", "streaming", "real-time", "dlt", "structured streaming", "live", "continuous"],
        "negative_keywords": ["no", "not", "batch only", "haven't", "planning", "none", "scheduled"],
    },
    {
        "id": "q_p7_02",
        "pillar": "P7",
        "text": "Is Change Data Capture (CDF) enabled on your Delta tables?",
        "criteria_ids": ["P7.4"],
        "services": ["delta_lake", "delta_live_tables"],
        "scoring_logic": "binary",
        "positive_keywords": ["yes", "cdf", "cdc", "enabled", "change data", "feed", "incremental"],
        "negative_keywords": ["no", "not", "disabled", "haven't", "full reload", "batch", "none"],
    },
    {
        "id": "q_p7_03",
        "pillar": "P7",
        "text": "Are your production pipelines scheduled with freshness SLAs?",
        "criteria_ids": ["P7.3", "P7.6"],
        "services": ["databricks_workflows", "delta_live_tables"],
        "scoring_logic": "analog",
        "positive_keywords": ["yes", "sla", "scheduled", "freshness", "all", "monitored", "defined"],
        "negative_keywords": ["no", "not", "some", "few", "ad-hoc", "manual", "none", "haven't"],
    },
]


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def get_questions_for_pillar(pillar: str) -> list[dict]:
    """Return all questions for a given pillar.

    Args:
        pillar: Pillar code string (e.g., "P1", "P3", "P4", "P5", "P6", "P7").

    Returns:
        List of question dicts belonging to the specified pillar.
        Empty list if no questions exist for that pillar.
    """
    return [q for q in DATABRICKS_QUESTION_BANK if q["pillar"] == pillar]


def get_unanswered_questions(
    pillar: str,
    scored_criteria: set[str],
) -> list[dict]:
    """Return questions where at least one linked criterion hasn't been scored.

    Questions are suppressed when all their linked criteria have already been
    scored (e.g., from document evidence), since asking them would be redundant.

    Args:
        pillar: Pillar code string (e.g., "P1").
        scored_criteria: Set of criteria IDs already scored (e.g., {"P1.1", "P1.5"}).

    Returns:
        List of question dicts that still have at least one unscored linked criterion.
    """
    pillar_questions = get_questions_for_pillar(pillar)
    unanswered: list[dict] = []
    for question in pillar_questions:
        # If at least one linked criterion is NOT yet scored, include the question
        if not all(cid in scored_criteria for cid in question["criteria_ids"]):
            unanswered.append(question)
    return unanswered

"""
FORGE 2.3 Assessment Workbench — Criteria Registry

Source of truth for all 142 FORGE criteria definitions. Each criterion is
mapped to its pillar (P1–P9), index, human-readable name, scoring type
(analog or binary), and the AWS services it depends on for assessment.

Usage:
    from forge.criteria_registry import CRITERIA_REGISTRY
    for criterion in CRITERIA_REGISTRY:
        print(f"{criterion.pillar}.{criterion.index} {criterion.name}")
"""
from __future__ import annotations

from forge.models import CriterionDefinition, CriterionType


# ---------------------------------------------------------------------------
# P1: Agent Access & Discovery (21 criteria)
# ---------------------------------------------------------------------------
_P1_CRITERIA = [
    CriterionDefinition(
        pillar="P1", index=1,
        name="API queryable",
        criterion_type=CriterionType.BINARY,
        services=["glue"],
    ),
    CriterionDefinition(
        pillar="P1", index=2,
        name="Catalog REST API",
        criterion_type=CriterionType.BINARY,
        services=["glue", "s3"],
    ),
    CriterionDefinition(
        pillar="P1", index=3,
        name="Schema introspection",
        criterion_type=CriterionType.BINARY,
        services=["glue"],
    ),
    CriterionDefinition(
        pillar="P1", index=4,
        name="MCP/tool interface",
        criterion_type=CriterionType.BINARY,
        services=["lambda", "bedrock"],
    ),
    CriterionDefinition(
        pillar="P1", index=5,
        name="Machine identity auth",
        criterion_type=CriterionType.BINARY,
        services=["iam"],
    ),
    CriterionDefinition(
        pillar="P1", index=6,
        name="Catalog covers >80%",
        criterion_type=CriterionType.ANALOG,
        services=["glue"],
    ),
    CriterionDefinition(
        pillar="P1", index=7,
        name="Catalog descriptions >80%",
        criterion_type=CriterionType.ANALOG,
        services=["glue"],
    ),
    CriterionDefinition(
        pillar="P1", index=8,
        name="Domain namespaces",
        criterion_type=CriterionType.BINARY,
        services=["glue"],
    ),
    CriterionDefinition(
        pillar="P1", index=9,
        name="Cross-engine discovery",
        criterion_type=CriterionType.BINARY,
        services=["athena", "redshift"],
    ),
    CriterionDefinition(
        pillar="P1", index=10,
        name="Auto-refreshed metadata",
        criterion_type=CriterionType.BINARY,
        services=["glue"],
    ),
    CriterionDefinition(
        pillar="P1", index=11,
        name="Open table format",
        criterion_type=CriterionType.BINARY,
        services=["glue", "s3"],
    ),
    CriterionDefinition(
        pillar="P1", index=12,
        name="Storage separated",
        criterion_type=CriterionType.BINARY,
        services=["s3"],
    ),
    CriterionDefinition(
        pillar="P1", index=13,
        name="Zero-copy read path",
        criterion_type=CriterionType.BINARY,
        services=["lakeformation"],
    ),
    CriterionDefinition(
        pillar="P1", index=14,
        name="Multi-engine access",
        criterion_type=CriterionType.BINARY,
        services=["athena", "redshift"],
    ),
    CriterionDefinition(
        pillar="P1", index=15,
        name="Version history",
        criterion_type=CriterionType.BINARY,
        services=["glue", "s3"],
    ),
    CriterionDefinition(
        pillar="P1", index=16,
        name="Relational DB accessible",
        criterion_type=CriterionType.BINARY,
        services=["rds"],
    ),
    CriterionDefinition(
        pillar="P1", index=17,
        name="NoSQL accessible",
        criterion_type=CriterionType.BINARY,
        services=["dynamodb"],
    ),
    CriterionDefinition(
        pillar="P1", index=18,
        name="Unstructured metadata",
        criterion_type=CriterionType.ANALOG,
        services=["s3"],
    ),
    CriterionDefinition(
        pillar="P1", index=19,
        name="Federated query",
        criterion_type=CriterionType.BINARY,
        services=["athena"],
    ),
    CriterionDefinition(
        pillar="P1", index=20,
        name="Operational DB cross-boundary",
        criterion_type=CriterionType.BINARY,
        services=["athena", "rds"],
    ),
    CriterionDefinition(
        pillar="P1", index=21,
        name="Governance on federated",
        criterion_type=CriterionType.BINARY,
        services=["lakeformation", "athena"],
    ),
]


# ---------------------------------------------------------------------------
# P2: Semantic Context & Retrieval (17 criteria)
# ---------------------------------------------------------------------------
_P2_CRITERIA = [
    CriterionDefinition(
        pillar="P2", index=1,
        name="Business glossary exists",
        criterion_type=CriterionType.BINARY,
        services=["glue", "sagemaker"],
    ),
    CriterionDefinition(
        pillar="P2", index=2,
        name="Terms linked to tables",
        criterion_type=CriterionType.BINARY,
        services=["glue", "sagemaker"],
    ),
    CriterionDefinition(
        pillar="P2", index=3,
        name="Glossary covers >50%",
        criterion_type=CriterionType.ANALOG,
        services=["glue", "sagemaker"],
    ),
    CriterionDefinition(
        pillar="P2", index=4,
        name="Glossary maintained <90d",
        criterion_type=CriterionType.BINARY,
        services=["glue", "sagemaker"],
    ),
    CriterionDefinition(
        pillar="P2", index=5,
        name="Entity relationships defined",
        criterion_type=CriterionType.BINARY,
        services=["neptune"],
    ),
    CriterionDefinition(
        pillar="P2", index=6,
        name="Hierarchies modeled",
        criterion_type=CriterionType.BINARY,
        services=["neptune"],
    ),
    CriterionDefinition(
        pillar="P2", index=7,
        name="Synonym mapping",
        criterion_type=CriterionType.BINARY,
        services=["glue", "sagemaker"],
    ),
    CriterionDefinition(
        pillar="P2", index=8,
        name="Relationships queryable",
        criterion_type=CriterionType.BINARY,
        services=["neptune"],
    ),
    CriterionDefinition(
        pillar="P2", index=9,
        name="Column descriptions >50%",
        criterion_type=CriterionType.ANALOG,
        services=["glue"],
    ),
    CriterionDefinition(
        pillar="P2", index=10,
        name="Data domains defined",
        criterion_type=CriterionType.BINARY,
        services=["glue"],
    ),
    CriterionDefinition(
        pillar="P2", index=11,
        name="Ownership assigned",
        criterion_type=CriterionType.BINARY,
        services=[],
    ),
    CriterionDefinition(
        pillar="P2", index=12,
        name="Business context via API",
        criterion_type=CriterionType.BINARY,
        services=["glue"],
    ),
    CriterionDefinition(
        pillar="P2", index=13,
        name="Vector embeddings exist",
        criterion_type=CriterionType.BINARY,
        services=["bedrock-agent"],
    ),
    CriterionDefinition(
        pillar="P2", index=14,
        name="Hybrid search available",
        criterion_type=CriterionType.BINARY,
        services=["opensearch", "bedrock-agent"],
    ),
    CriterionDefinition(
        pillar="P2", index=15,
        name="GraphRAG available",
        criterion_type=CriterionType.BINARY,
        services=["neptune", "bedrock-agent"],
    ),
    CriterionDefinition(
        pillar="P2", index=16,
        name="Text-to-SQL path",
        criterion_type=CriterionType.BINARY,
        services=["bedrock-agent"],
    ),
    CriterionDefinition(
        pillar="P2", index=17,
        name="Retrieval accuracy evaluated",
        criterion_type=CriterionType.BINARY,
        services=["bedrock-agent"],
    ),
]


# ---------------------------------------------------------------------------
# P3: Data Lineage & Provenance (14 criteria)
# ---------------------------------------------------------------------------
_P3_CRITERIA = [
    CriterionDefinition(
        pillar="P3", index=1,
        name="Source-to-consumption lineage",
        criterion_type=CriterionType.ANALOG,
        services=["sagemaker", "glue"],
    ),
    CriterionDefinition(
        pillar="P3", index=2,
        name="Lineage captures transforms",
        criterion_type=CriterionType.BINARY,
        services=["glue"],
    ),
    CriterionDefinition(
        pillar="P3", index=3,
        name="Auto-updated lineage",
        criterion_type=CriterionType.BINARY,
        services=["sagemaker"],
    ),
    CriterionDefinition(
        pillar="P3", index=4,
        name="Multi-engine lineage",
        criterion_type=CriterionType.BINARY,
        services=["sagemaker", "glue"],
    ),
    CriterionDefinition(
        pillar="P3", index=5,
        name="Queryable via API",
        criterion_type=CriterionType.BINARY,
        services=["sagemaker"],
    ),
    CriterionDefinition(
        pillar="P3", index=6,
        name="OpenLineage standard",
        criterion_type=CriterionType.BINARY,
        services=["glue"],
    ),
    CriterionDefinition(
        pillar="P3", index=7,
        name="Column-level lineage",
        criterion_type=CriterionType.BINARY,
        services=["sagemaker"],
    ),
    CriterionDefinition(
        pillar="P3", index=8,
        name="Timestamps on events",
        criterion_type=CriterionType.BINARY,
        services=["sagemaker", "glue"],
    ),
    CriterionDefinition(
        pillar="P3", index=9,
        name="Freshness tracked",
        criterion_type=CriterionType.BINARY,
        services=["glue"],
    ),
    CriterionDefinition(
        pillar="P3", index=10,
        name="Source system identified",
        criterion_type=CriterionType.BINARY,
        services=["glue"],
    ),
    CriterionDefinition(
        pillar="P3", index=11,
        name="Transformation logic linked",
        criterion_type=CriterionType.BINARY,
        services=["glue"],
    ),
    CriterionDefinition(
        pillar="P3", index=12,
        name="Lineage immutable",
        criterion_type=CriterionType.BINARY,
        services=["s3"],
    ),
    CriterionDefinition(
        pillar="P3", index=13,
        name="Vector index audit trail",
        criterion_type=CriterionType.BINARY,
        services=["bedrock-agent"],
    ),
    CriterionDefinition(
        pillar="P3", index=14,
        name="Right-to-be-forgotten",
        criterion_type=CriterionType.BINARY,
        services=["bedrock-agent"],
    ),
]


# ---------------------------------------------------------------------------
# P4: Data Quality, Contracts & Classification (18 criteria)
# ---------------------------------------------------------------------------
_P4_CRITERIA = [
    CriterionDefinition(
        pillar="P4", index=1,
        name="Quality rules defined",
        criterion_type=CriterionType.BINARY,
        services=["glue"],
    ),
    CriterionDefinition(
        pillar="P4", index=2,
        name="Completeness checks",
        criterion_type=CriterionType.BINARY,
        services=["glue"],
    ),
    CriterionDefinition(
        pillar="P4", index=3,
        name="Uniqueness checks",
        criterion_type=CriterionType.BINARY,
        services=["glue"],
    ),
    CriterionDefinition(
        pillar="P4", index=4,
        name="Freshness checks",
        criterion_type=CriterionType.BINARY,
        services=["glue"],
    ),
    CriterionDefinition(
        pillar="P4", index=5,
        name="Referential integrity",
        criterion_type=CriterionType.BINARY,
        services=[],
    ),
    CriterionDefinition(
        pillar="P4", index=6,
        name="Business logic rules",
        criterion_type=CriterionType.BINARY,
        services=["glue"],
    ),
    CriterionDefinition(
        pillar="P4", index=7,
        name="Checks run automatically",
        criterion_type=CriterionType.BINARY,
        services=["glue", "events"],
    ),
    CriterionDefinition(
        pillar="P4", index=8,
        name="Quality scores stored",
        criterion_type=CriterionType.BINARY,
        services=["glue"],
    ),
    CriterionDefinition(
        pillar="P4", index=9,
        name="Scores in catalog",
        criterion_type=CriterionType.BINARY,
        services=["glue"],
    ),
    CriterionDefinition(
        pillar="P4", index=10,
        name="Alerts on drift",
        criterion_type=CriterionType.BINARY,
        services=["glue", "sns"],
    ),
    CriterionDefinition(
        pillar="P4", index=11,
        name="Certified flag",
        criterion_type=CriterionType.BINARY,
        services=["glue"],
    ),
    CriterionDefinition(
        pillar="P4", index=12,
        name="Score-based certification",
        criterion_type=CriterionType.BINARY,
        services=["glue"],
    ),
    CriterionDefinition(
        pillar="P4", index=13,
        name="Certification via API",
        criterion_type=CriterionType.BINARY,
        services=["glue"],
    ),
    CriterionDefinition(
        pillar="P4", index=14,
        name="PII/PHI detection",
        criterion_type=CriterionType.BINARY,
        services=["macie2"],
    ),
    CriterionDefinition(
        pillar="P4", index=15,
        name="Sensitivity labels",
        criterion_type=CriterionType.BINARY,
        services=["macie2", "glue"],
    ),
    CriterionDefinition(
        pillar="P4", index=16,
        name="Schema contracts",
        criterion_type=CriterionType.BINARY,
        services=["glue"],
    ),
    CriterionDefinition(
        pillar="P4", index=17,
        name="Breaking change alerts",
        criterion_type=CriterionType.BINARY,
        services=["glue"],
    ),
    CriterionDefinition(
        pillar="P4", index=18,
        name="Model trust scores",
        criterion_type=CriterionType.BINARY,
        services=["sagemaker"],
    ),
]


# ---------------------------------------------------------------------------
# P5: Access Control, Identity & Tenancy (17 criteria)
# ---------------------------------------------------------------------------
_P5_CRITERIA = [
    CriterionDefinition(
        pillar="P5", index=1,
        name="Column-level access",
        criterion_type=CriterionType.BINARY,
        services=["lakeformation"],
    ),
    CriterionDefinition(
        pillar="P5", index=2,
        name="Row-level filtering",
        criterion_type=CriterionType.BINARY,
        services=["lakeformation"],
    ),
    CriterionDefinition(
        pillar="P5", index=3,
        name="Dynamic masking",
        criterion_type=CriterionType.BINARY,
        services=["lakeformation"],
    ),
    CriterionDefinition(
        pillar="P5", index=4,
        name="Tag-based policies",
        criterion_type=CriterionType.BINARY,
        services=["lakeformation"],
    ),
    CriterionDefinition(
        pillar="P5", index=5,
        name="Agent IAM identities",
        criterion_type=CriterionType.BINARY,
        services=["iam"],
    ),
    CriterionDefinition(
        pillar="P5", index=6,
        name="Least-privilege",
        criterion_type=CriterionType.BINARY,
        services=["iam", "accessanalyzer"],
    ),
    CriterionDefinition(
        pillar="P5", index=7,
        name="Identity chain traceable",
        criterion_type=CriterionType.BINARY,
        services=["cloudtrail"],
    ),
    CriterionDefinition(
        pillar="P5", index=8,
        name="Agent access revocable",
        criterion_type=CriterionType.BINARY,
        services=["iam"],
    ),
    CriterionDefinition(
        pillar="P5", index=9,
        name="Policies as code",
        criterion_type=CriterionType.BINARY,
        services=["cloudformation"],
    ),
    CriterionDefinition(
        pillar="P5", index=10,
        name="Version-controlled",
        criterion_type=CriterionType.BINARY,
        services=["cloudformation"],
    ),
    CriterionDefinition(
        pillar="P5", index=11,
        name="Policy evaluation auditable",
        criterion_type=CriterionType.BINARY,
        services=["lakeformation"],
    ),
    CriterionDefinition(
        pillar="P5", index=12,
        name="Cross-account governed",
        criterion_type=CriterionType.BINARY,
        services=["cloudtrail", "s3"],
    ),
    CriterionDefinition(
        pillar="P5", index=13,
        name="Cedar/OPA policies",
        criterion_type=CriterionType.BINARY,
        services=[],
    ),
    CriterionDefinition(
        pillar="P5", index=14,
        name="Request-time evaluation",
        criterion_type=CriterionType.BINARY,
        services=["lakeformation"],
    ),
    CriterionDefinition(
        pillar="P5", index=15,
        name="Agent identity at protocol",
        criterion_type=CriterionType.BINARY,
        services=["lakeformation", "iam"],
    ),
    CriterionDefinition(
        pillar="P5", index=16,
        name="Multi-tenant isolation",
        criterion_type=CriterionType.BINARY,
        services=["lakeformation"],
    ),
    CriterionDefinition(
        pillar="P5", index=17,
        name="Per-tenant cost attribution",
        criterion_type=CriterionType.BINARY,
        services=["cost-explorer"],
    ),
]


# ---------------------------------------------------------------------------
# P6: Observability & Audit (12 criteria)
# ---------------------------------------------------------------------------
_P6_CRITERIA = [
    CriterionDefinition(
        pillar="P6", index=1,
        name="Agent-to-data logged",
        criterion_type=CriterionType.BINARY,
        services=["cloudtrail"],
    ),
    CriterionDefinition(
        pillar="P6", index=2,
        name="Intent context in logs",
        criterion_type=CriterionType.BINARY,
        services=[],
    ),
    CriterionDefinition(
        pillar="P6", index=3,
        name="Distributed tracing",
        criterion_type=CriterionType.BINARY,
        services=["xray", "cloudwatch"],
    ),
    CriterionDefinition(
        pillar="P6", index=4,
        name="Open standard traces",
        criterion_type=CriterionType.BINARY,
        services=["xray"],
    ),
    CriterionDefinition(
        pillar="P6", index=5,
        name="Per-agent cost measurable",
        criterion_type=CriterionType.BINARY,
        services=["cost-explorer"],
    ),
    CriterionDefinition(
        pillar="P6", index=6,
        name="Per-query cost attributable",
        criterion_type=CriterionType.BINARY,
        services=["athena"],
    ),
    CriterionDefinition(
        pillar="P6", index=7,
        name="Cost anomaly detection",
        criterion_type=CriterionType.BINARY,
        services=["cost-explorer"],
    ),
    CriterionDefinition(
        pillar="P6", index=8,
        name="Audit queryable SQL",
        criterion_type=CriterionType.BINARY,
        services=["cloudtrail", "athena"],
    ),
    CriterionDefinition(
        pillar="P6", index=9,
        name="Machine access logged",
        criterion_type=CriterionType.BINARY,
        services=["cloudtrail"],
    ),
    CriterionDefinition(
        pillar="P6", index=10,
        name="Data-layer access logged",
        criterion_type=CriterionType.BINARY,
        services=["cloudtrail"],
    ),
    CriterionDefinition(
        pillar="P6", index=11,
        name="Config/Audit Manager",
        criterion_type=CriterionType.BINARY,
        services=["config"],
    ),
    CriterionDefinition(
        pillar="P6", index=12,
        name="Regulatory evidence",
        criterion_type=CriterionType.BINARY,
        services=["config", "cloudtrail"],
    ),
]


# ---------------------------------------------------------------------------
# P7: Real-Time, Freshness & Zero-ETL (15 criteria)
# ---------------------------------------------------------------------------
_P7_CRITERIA = [
    CriterionDefinition(
        pillar="P7", index=1,
        name="Real-time dataset",
        criterion_type=CriterionType.BINARY,
        services=["kinesis", "msk"],
    ),
    CriterionDefinition(
        pillar="P7", index=2,
        name="Freshness SLAs",
        criterion_type=CriterionType.ANALOG,
        services=["glue"],
    ),
    CriterionDefinition(
        pillar="P7", index=3,
        name="Freshness queryable",
        criterion_type=CriterionType.BINARY,
        services=["glue"],
    ),
    CriterionDefinition(
        pillar="P7", index=4,
        name="Agents verify freshness",
        criterion_type=CriterionType.BINARY,
        services=["glue"],
    ),
    CriterionDefinition(
        pillar="P7", index=5,
        name="Streaming layer exists",
        criterion_type=CriterionType.BINARY,
        services=["kinesis", "msk"],
    ),
    CriterionDefinition(
        pillar="P7", index=6,
        name="Streaming to cataloged storage",
        criterion_type=CriterionType.BINARY,
        services=["kinesis", "msk", "glue"],
    ),
    CriterionDefinition(
        pillar="P7", index=7,
        name="Streaming lineage",
        criterion_type=CriterionType.BINARY,
        services=[],
    ),
    CriterionDefinition(
        pillar="P7", index=8,
        name="Streaming DQ enforcement",
        criterion_type=CriterionType.BINARY,
        services=["glue", "kinesis"],
    ),
    CriterionDefinition(
        pillar="P7", index=9,
        name="Schema change alerts",
        criterion_type=CriterionType.BINARY,
        services=["glue"],
    ),
    CriterionDefinition(
        pillar="P7", index=10,
        name="Data drift monitored",
        criterion_type=CriterionType.BINARY,
        services=["glue"],
    ),
    CriterionDefinition(
        pillar="P7", index=11,
        name="Time-travel supported",
        criterion_type=CriterionType.BINARY,
        services=["glue", "s3"],
    ),
    CriterionDefinition(
        pillar="P7", index=12,
        name="Change notifications",
        criterion_type=CriterionType.BINARY,
        services=["events"],
    ),
    CriterionDefinition(
        pillar="P7", index=13,
        name="Zero-ETL exists",
        criterion_type=CriterionType.BINARY,
        services=["rds"],
    ),
    CriterionDefinition(
        pillar="P7", index=14,
        name="Zero-ETL governed",
        criterion_type=CriterionType.BINARY,
        services=["rds", "lakeformation"],
    ),
    CriterionDefinition(
        pillar="P7", index=15,
        name="Embedding refresh schedule",
        criterion_type=CriterionType.BINARY,
        services=["bedrock-agent"],
    ),
]


# ---------------------------------------------------------------------------
# P8: Agent Controllability & Policy (16 criteria)
# ---------------------------------------------------------------------------
_P8_CRITERIA = [
    CriterionDefinition(
        pillar="P8", index=1,
        name="Content filtering",
        criterion_type=CriterionType.BINARY,
        services=["bedrock"],
    ),
    CriterionDefinition(
        pillar="P8", index=2,
        name="Topic restrictions",
        criterion_type=CriterionType.BINARY,
        services=["bedrock"],
    ),
    CriterionDefinition(
        pillar="P8", index=3,
        name="Rate limiting",
        criterion_type=CriterionType.BINARY,
        services=["apigateway"],
    ),
    CriterionDefinition(
        pillar="P8", index=4,
        name="Kill switch",
        criterion_type=CriterionType.BINARY,
        services=["iam"],
    ),
    CriterionDefinition(
        pillar="P8", index=5,
        name="Policies as code",
        criterion_type=CriterionType.BINARY,
        services=[],
    ),
    CriterionDefinition(
        pillar="P8", index=6,
        name="Dry-run available",
        criterion_type=CriterionType.BINARY,
        services=[],
    ),
    CriterionDefinition(
        pillar="P8", index=7,
        name="Violations alerted",
        criterion_type=CriterionType.BINARY,
        services=["cloudwatch"],
    ),
    CriterionDefinition(
        pillar="P8", index=8,
        name="Policies portable",
        criterion_type=CriterionType.BINARY,
        services=[],
    ),
    CriterionDefinition(
        pillar="P8", index=9,
        name="Human approval required",
        criterion_type=CriterionType.BINARY,
        services=["stepfunctions"],
    ),
    CriterionDefinition(
        pillar="P8", index=10,
        name="Escalation path",
        criterion_type=CriterionType.BINARY,
        services=["sns"],
    ),
    CriterionDefinition(
        pillar="P8", index=11,
        name="Timeout/circuit-breaker",
        criterion_type=CriterionType.BINARY,
        services=["stepfunctions", "apigateway"],
    ),
    CriterionDefinition(
        pillar="P8", index=12,
        name="Actions auditable",
        criterion_type=CriterionType.BINARY,
        services=["cloudtrail"],
    ),
    CriterionDefinition(
        pillar="P8", index=13,
        name="Policy at data layer",
        criterion_type=CriterionType.BINARY,
        services=["lakeformation"],
    ),
    CriterionDefinition(
        pillar="P8", index=14,
        name="Policy at tool layer",
        criterion_type=CriterionType.BINARY,
        services=[],
    ),
    CriterionDefinition(
        pillar="P8", index=15,
        name="Policy at output layer",
        criterion_type=CriterionType.BINARY,
        services=["bedrock"],
    ),
    CriterionDefinition(
        pillar="P8", index=16,
        name="Policy at action layer",
        criterion_type=CriterionType.BINARY,
        services=["stepfunctions"],
    ),
]


# ---------------------------------------------------------------------------
# P9: Decision Lineage & Explainability (12 criteria)
# ---------------------------------------------------------------------------
_P9_CRITERIA = [
    CriterionDefinition(
        pillar="P9", index=1,
        name="Reasoning steps recorded",
        criterion_type=CriterionType.BINARY,
        services=["bedrock", "cloudwatch"],
    ),
    CriterionDefinition(
        pillar="P9", index=2,
        name="Decision links to sources",
        criterion_type=CriterionType.BINARY,
        services=["bedrock"],
    ),
    CriterionDefinition(
        pillar="P9", index=3,
        name="Intermediate reasoning",
        criterion_type=CriterionType.BINARY,
        services=["bedrock"],
    ),
    CriterionDefinition(
        pillar="P9", index=4,
        name="Decision chain queryable",
        criterion_type=CriterionType.BINARY,
        services=["cloudwatch"],
    ),
    CriterionDefinition(
        pillar="P9", index=5,
        name="Full path reconstructable",
        criterion_type=CriterionType.BINARY,
        services=["bedrock", "cloudwatch"],
    ),
    CriterionDefinition(
        pillar="P9", index=6,
        name="Data-to-decision attribution",
        criterion_type=CriterionType.BINARY,
        services=[],
    ),
    CriterionDefinition(
        pillar="P9", index=7,
        name="Confidence quantified",
        criterion_type=CriterionType.BINARY,
        services=[],
    ),
    CriterionDefinition(
        pillar="P9", index=8,
        name="Alternatives logged",
        criterion_type=CriterionType.BINARY,
        services=[],
    ),
    CriterionDefinition(
        pillar="P9", index=9,
        name="Outcomes tracked",
        criterion_type=CriterionType.BINARY,
        services=[],
    ),
    CriterionDefinition(
        pillar="P9", index=10,
        name="Human review possible",
        criterion_type=CriterionType.BINARY,
        services=["bedrock", "cloudwatch"],
    ),
    CriterionDefinition(
        pillar="P9", index=11,
        name="Decision lineage immutable",
        criterion_type=CriterionType.BINARY,
        services=["s3"],
    ),
    CriterionDefinition(
        pillar="P9", index=12,
        name="Regulatory evidence <10min",
        criterion_type=CriterionType.BINARY,
        services=["cloudwatch"],
    ),
]


# ---------------------------------------------------------------------------
# Combined registry: all 142 criteria in pillar order
# ---------------------------------------------------------------------------
CRITERIA_REGISTRY: list[CriterionDefinition] = (
    _P1_CRITERIA
    + _P2_CRITERIA
    + _P3_CRITERIA
    + _P4_CRITERIA
    + _P5_CRITERIA
    + _P6_CRITERIA
    + _P7_CRITERIA
    + _P8_CRITERIA
    + _P9_CRITERIA
)


# ---------------------------------------------------------------------------
# Convenience lookups
# ---------------------------------------------------------------------------

#: Pillar display names keyed by code
PILLAR_NAMES: dict[str, str] = {
    "P1": "Agent Access & Discovery",
    "P2": "Semantic Context & Retrieval",
    "P3": "Data Lineage & Provenance",
    "P4": "Data Quality, Contracts & Classification",
    "P5": "Access Control, Identity & Tenancy",
    "P6": "Observability & Audit",
    "P7": "Real-Time, Freshness & Zero-ETL",
    "P8": "Agent Controllability & Policy",
    "P9": "Decision Lineage & Explainability",
}

#: Expected criterion counts per pillar
PILLAR_CRITERIA_COUNTS: dict[str, int] = {
    "P1": 21, "P2": 17, "P3": 14, "P4": 18,
    "P5": 17, "P6": 12, "P7": 15, "P8": 16, "P9": 12,
}


def get_criteria_for_pillar(pillar: str) -> list[CriterionDefinition]:
    """Return all criteria belonging to a specific pillar code (e.g., 'P1')."""
    return [c for c in CRITERIA_REGISTRY if c.pillar == pillar]


def get_criterion(pillar: str, index: int) -> CriterionDefinition | None:
    """Look up a single criterion by pillar and index. Returns None if not found."""
    for c in CRITERIA_REGISTRY:
        if c.pillar == pillar and c.index == index:
            return c
    return None


def get_all_services() -> set[str]:
    """Return the set of all unique AWS service names referenced across all criteria."""
    services: set[str] = set()
    for c in CRITERIA_REGISTRY:
        services.update(c.services)
    return services

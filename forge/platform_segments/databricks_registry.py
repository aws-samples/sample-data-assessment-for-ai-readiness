"""
FORGE 2.3 Assessment Workbench — Databricks Criteria Registry

Source of truth for Databricks-specific FORGE criteria definitions. Each criterion
is mapped to its pillar (P1–P9), index, human-readable name, scoring type
(analog or binary), and the Databricks services it depends on for assessment.

Applicable pillars for Databricks: P1, P3, P4, P5, P6, P7.

Usage:
    from forge.platform_segments.databricks_registry import (
        DATABRICKS_CRITERIA_REGISTRY,
        DATABRICKS_SERVICES,
        get_databricks_criteria_for_pillar,
        get_databricks_criterion,
        get_all_databricks_services,
    )
"""
from __future__ import annotations

from forge.models import CriterionDefinition, CriterionType


# ---------------------------------------------------------------------------
# Databricks Service Mapping (service_key → display_name)
# ---------------------------------------------------------------------------

DATABRICKS_SERVICES: dict[str, str] = {
    "unity_catalog": "Unity Catalog",
    "unity_catalog_lineage": "UC Lineage",
    "delta_live_tables": "Delta Live Tables",
    "delta_lake": "Delta Lake",
    "sql_warehouse": "SQL Warehouse",
    "mlflow": "MLflow",
    "databricks_workflows": "Workflows",
    "structured_streaming": "Structured Streaming",
    "system_tables": "System Tables (Audit)",
    "model_serving": "Model Serving",
}


# ---------------------------------------------------------------------------
# P1: Agent Access & Discovery (10 criteria)
# ---------------------------------------------------------------------------
_P1_CRITERIA = [
    CriterionDefinition(
        pillar="P1", index=1,
        name="Unity Catalog API queryable",
        criterion_type=CriterionType.BINARY,
        services=["unity_catalog"],
        description="Unity Catalog REST API accessible for programmatic catalog queries",
    ),
    CriterionDefinition(
        pillar="P1", index=2,
        name="Tables discoverable via UC",
        criterion_type=CriterionType.ANALOG,
        services=["unity_catalog"],
        description="Percentage of tables registered in Unity Catalog vs total",
    ),
    CriterionDefinition(
        pillar="P1", index=3,
        name="Schema introspection via UC",
        criterion_type=CriterionType.BINARY,
        services=["unity_catalog"],
        description="Column-level schema metadata queryable through Unity Catalog API",
    ),
    CriterionDefinition(
        pillar="P1", index=4,
        name="Catalog descriptions populated",
        criterion_type=CriterionType.ANALOG,
        services=["unity_catalog"],
        description="Percentage of UC tables and columns with human-readable descriptions",
    ),
    CriterionDefinition(
        pillar="P1", index=5,
        name="Three-level namespace used",
        criterion_type=CriterionType.BINARY,
        services=["unity_catalog"],
        description="Catalog/schema/table namespace hierarchy actively enforced for organization",
    ),
    CriterionDefinition(
        pillar="P1", index=6,
        name="Delta Lake open format",
        criterion_type=CriterionType.BINARY,
        services=["delta_lake"],
        description="Tables stored in Delta Lake open format enabling multi-engine access",
    ),
    CriterionDefinition(
        pillar="P1", index=7,
        name="External locations governed",
        criterion_type=CriterionType.BINARY,
        services=["unity_catalog"],
        description="External storage locations registered and governed through Unity Catalog",
    ),
    CriterionDefinition(
        pillar="P1", index=8,
        name="Cross-workspace discovery",
        criterion_type=CriterionType.BINARY,
        services=["unity_catalog"],
        description="Metastore shared across workspaces allowing cross-workspace table discovery",
    ),
    CriterionDefinition(
        pillar="P1", index=9,
        name="SQL Warehouse query access",
        criterion_type=CriterionType.BINARY,
        services=["sql_warehouse", "unity_catalog"],
        description="SQL Warehouse endpoints available for programmatic agent SQL queries",
    ),
    CriterionDefinition(
        pillar="P1", index=10,
        name="Delta time-travel enabled",
        criterion_type=CriterionType.BINARY,
        services=["delta_lake"],
        description="Delta Lake time-travel capability available for versioned data access",
    ),
]


# ---------------------------------------------------------------------------
# P3: Data Lineage & Provenance (9 criteria)
# ---------------------------------------------------------------------------
_P3_CRITERIA = [
    CriterionDefinition(
        pillar="P3", index=1,
        name="UC lineage tracking enabled",
        criterion_type=CriterionType.BINARY,
        services=["unity_catalog_lineage"],
        description="Unity Catalog lineage capture is enabled for table-level tracking",
    ),
    CriterionDefinition(
        pillar="P3", index=2,
        name="Column-level lineage captured",
        criterion_type=CriterionType.BINARY,
        services=["unity_catalog_lineage"],
        description="Column-level lineage automatically captured through UC lineage",
    ),
    CriterionDefinition(
        pillar="P3", index=3,
        name="Lineage coverage",
        criterion_type=CriterionType.ANALOG,
        services=["unity_catalog_lineage"],
        description="Percentage of production tables with lineage captured in Unity Catalog",
    ),
    CriterionDefinition(
        pillar="P3", index=4,
        name="Lineage queryable via API",
        criterion_type=CriterionType.BINARY,
        services=["unity_catalog_lineage"],
        description="Lineage information accessible programmatically via UC REST API",
    ),
    CriterionDefinition(
        pillar="P3", index=5,
        name="DLT pipeline lineage",
        criterion_type=CriterionType.BINARY,
        services=["delta_live_tables", "unity_catalog_lineage"],
        description="Delta Live Tables pipeline lineage automatically captured end-to-end",
    ),
    CriterionDefinition(
        pillar="P3", index=6,
        name="Notebook lineage coverage",
        criterion_type=CriterionType.ANALOG,
        services=["unity_catalog_lineage"],
        description="Percentage of production notebooks with lineage captured in Unity Catalog",
    ),
    CriterionDefinition(
        pillar="P3", index=7,
        name="Workflow job lineage",
        criterion_type=CriterionType.BINARY,
        services=["databricks_workflows", "unity_catalog_lineage"],
        description="Lineage from Databricks Workflow job runs captured automatically",
    ),
    CriterionDefinition(
        pillar="P3", index=8,
        name="MLflow model lineage",
        criterion_type=CriterionType.BINARY,
        services=["mlflow", "unity_catalog_lineage"],
        description="MLflow model artifacts linked to training data via lineage graph",
    ),
    CriterionDefinition(
        pillar="P3", index=9,
        name="Lineage freshness tracked",
        criterion_type=CriterionType.ANALOG,
        services=["unity_catalog_lineage"],
        description="Percentage of lineage records updated within the last 7 days",
    ),
]


# ---------------------------------------------------------------------------
# P4: Data Quality, Contracts & Classification (10 criteria)
# ---------------------------------------------------------------------------
_P4_CRITERIA = [
    CriterionDefinition(
        pillar="P4", index=1,
        name="DLT expectations configured",
        criterion_type=CriterionType.BINARY,
        services=["delta_live_tables"],
        description="Delta Live Tables expectations (DQ rules) exist on production pipelines",
    ),
    CriterionDefinition(
        pillar="P4", index=2,
        name="Tables with DQ rules",
        criterion_type=CriterionType.ANALOG,
        services=["delta_live_tables"],
        description="Percentage of production tables with DLT expectations or DQ monitors",
    ),
    CriterionDefinition(
        pillar="P4", index=3,
        name="Pipelines with automated DQ",
        criterion_type=CriterionType.ANALOG,
        services=["delta_live_tables", "databricks_workflows"],
        description="Percentage of production pipelines with automated DQ checks on each run",
    ),
    CriterionDefinition(
        pillar="P4", index=4,
        name="Quality metrics stored",
        criterion_type=CriterionType.BINARY,
        services=["delta_live_tables", "system_tables"],
        description="DQ expectation results stored in system tables for historical trending",
    ),
    CriterionDefinition(
        pillar="P4", index=5,
        name="Schema enforcement enabled",
        criterion_type=CriterionType.BINARY,
        services=["delta_lake"],
        description="Delta Lake schema enforcement active preventing malformed writes",
    ),
    CriterionDefinition(
        pillar="P4", index=6,
        name="Schema evolution managed",
        criterion_type=CriterionType.BINARY,
        services=["delta_lake"],
        description="Schema evolution changes tracked and gated through merge schema controls",
    ),
    CriterionDefinition(
        pillar="P4", index=7,
        name="PII tags applied",
        criterion_type=CriterionType.ANALOG,
        services=["unity_catalog"],
        description="Percentage of sensitive columns tagged with PII/PHI classification in UC",
    ),
    CriterionDefinition(
        pillar="P4", index=8,
        name="DQ alerts configured",
        criterion_type=CriterionType.BINARY,
        services=["delta_live_tables", "databricks_workflows"],
        description="Alerts configured to fire when DLT expectations fail on production data",
    ),
    CriterionDefinition(
        pillar="P4", index=9,
        name="Table constraints defined",
        criterion_type=CriterionType.BINARY,
        services=["delta_lake", "unity_catalog"],
        description="NOT NULL, CHECK, or PRIMARY KEY constraints defined on Delta tables",
    ),
    CriterionDefinition(
        pillar="P4", index=10,
        name="Model validation gates",
        criterion_type=CriterionType.BINARY,
        services=["mlflow", "model_serving"],
        description="ML models require validation gate (tests passing) before promotion to production",
    ),
]


# ---------------------------------------------------------------------------
# P5: Access Control, Identity & Tenancy (10 criteria)
# ---------------------------------------------------------------------------
_P5_CRITERIA = [
    CriterionDefinition(
        pillar="P5", index=1,
        name="UC column-level masking",
        criterion_type=CriterionType.BINARY,
        services=["unity_catalog"],
        description="Column-level dynamic masking configured in Unity Catalog",
    ),
    CriterionDefinition(
        pillar="P5", index=2,
        name="Row-level security",
        criterion_type=CriterionType.BINARY,
        services=["unity_catalog"],
        description="Row filters applied in Unity Catalog for tenant-level data isolation",
    ),
    CriterionDefinition(
        pillar="P5", index=3,
        name="UC permissions model used",
        criterion_type=CriterionType.BINARY,
        services=["unity_catalog"],
        description="Unity Catalog GRANT/REVOKE permissions model actively used (not legacy ACLs)",
    ),
    CriterionDefinition(
        pillar="P5", index=4,
        name="Service principal identities",
        criterion_type=CriterionType.BINARY,
        services=["unity_catalog"],
        description="Service principals configured for machine/agent access to Databricks",
    ),
    CriterionDefinition(
        pillar="P5", index=5,
        name="Least-privilege enforced",
        criterion_type=CriterionType.ANALOG,
        services=["unity_catalog"],
        description="Percentage of users/principals with narrowly scoped permissions (no workspace admin)",
    ),
    CriterionDefinition(
        pillar="P5", index=6,
        name="Token management",
        criterion_type=CriterionType.BINARY,
        services=["unity_catalog"],
        description="Personal access tokens restricted or managed via token policies",
    ),
    CriterionDefinition(
        pillar="P5", index=7,
        name="Workspaces with IP restrictions",
        criterion_type=CriterionType.ANALOG,
        services=["unity_catalog"],
        description="Percentage of workspaces with IP access lists configured",
    ),
    CriterionDefinition(
        pillar="P5", index=8,
        name="Data access auditable",
        criterion_type=CriterionType.BINARY,
        services=["unity_catalog", "system_tables"],
        description="All data access through UC is logged and auditable via system tables",
    ),
    CriterionDefinition(
        pillar="P5", index=9,
        name="Cross-workspace isolation",
        criterion_type=CriterionType.BINARY,
        services=["unity_catalog"],
        description="Workspace-level isolation enforced through UC catalog bindings",
    ),
    CriterionDefinition(
        pillar="P5", index=10,
        name="Secure cluster policies",
        criterion_type=CriterionType.BINARY,
        services=["unity_catalog", "databricks_workflows"],
        description="Cluster policies enforce security settings (no credentials in env vars, UC-only access)",
    ),
]


# ---------------------------------------------------------------------------
# P6: Observability & Audit (9 criteria)
# ---------------------------------------------------------------------------
_P6_CRITERIA = [
    CriterionDefinition(
        pillar="P6", index=1,
        name="Audit logs enabled",
        criterion_type=CriterionType.BINARY,
        services=["system_tables"],
        description="Databricks system tables (audit logs) are active and queryable",
    ),
    CriterionDefinition(
        pillar="P6", index=2,
        name="Data access logged",
        criterion_type=CriterionType.BINARY,
        services=["system_tables", "unity_catalog"],
        description="All table reads/writes logged with user identity in audit system tables",
    ),
    CriterionDefinition(
        pillar="P6", index=3,
        name="Query history coverage",
        criterion_type=CriterionType.ANALOG,
        services=["sql_warehouse", "system_tables"],
        description="Percentage of SQL Warehouses with query history retention enabled",
    ),
    CriterionDefinition(
        pillar="P6", index=4,
        name="Cost per workspace measurable",
        criterion_type=CriterionType.BINARY,
        services=["system_tables"],
        description="Per-workspace or per-cluster cost attribution available via billing tables",
    ),
    CriterionDefinition(
        pillar="P6", index=5,
        name="Pipeline observability",
        criterion_type=CriterionType.BINARY,
        services=["delta_live_tables", "system_tables"],
        description="DLT pipeline run status, duration, and data quality metrics observable",
    ),
    CriterionDefinition(
        pillar="P6", index=6,
        name="MLflow experiment tracking",
        criterion_type=CriterionType.BINARY,
        services=["mlflow"],
        description="MLflow experiments tracked with metrics, parameters, and artifacts logged",
    ),
    CriterionDefinition(
        pillar="P6", index=7,
        name="Audit queryable via SQL",
        criterion_type=CriterionType.BINARY,
        services=["system_tables", "sql_warehouse"],
        description="Audit log system tables queryable via standard SQL for compliance reporting",
    ),
    CriterionDefinition(
        pillar="P6", index=8,
        name="Audit retention adequate",
        criterion_type=CriterionType.ANALOG,
        services=["system_tables"],
        description="Proportion of audit log retention meeting compliance requirements (≥365 days)",
    ),
    CriterionDefinition(
        pillar="P6", index=9,
        name="Model serving metrics",
        criterion_type=CriterionType.BINARY,
        services=["model_serving", "system_tables"],
        description="Model serving endpoint metrics (latency, throughput, errors) monitored",
    ),
]


# ---------------------------------------------------------------------------
# P7: Real-Time, Freshness & Zero-ETL (9 criteria)
# ---------------------------------------------------------------------------
_P7_CRITERIA = [
    CriterionDefinition(
        pillar="P7", index=1,
        name="Streaming tables in production",
        criterion_type=CriterionType.BINARY,
        services=["delta_live_tables", "structured_streaming"],
        description="Streaming tables or DLT streaming pipelines in production use",
    ),
    CriterionDefinition(
        pillar="P7", index=2,
        name="Structured Streaming active",
        criterion_type=CriterionType.BINARY,
        services=["structured_streaming"],
        description="Spark Structured Streaming jobs actively processing real-time data",
    ),
    CriterionDefinition(
        pillar="P7", index=3,
        name="Freshness SLAs defined",
        criterion_type=CriterionType.ANALOG,
        services=["delta_live_tables", "databricks_workflows"],
        description="Percentage of production tables with explicit freshness SLAs defined",
    ),
    CriterionDefinition(
        pillar="P7", index=4,
        name="Change Data Capture enabled",
        criterion_type=CriterionType.BINARY,
        services=["delta_lake", "delta_live_tables"],
        description="Change Data Feed enabled on Delta tables for incremental downstream processing",
    ),
    CriterionDefinition(
        pillar="P7", index=5,
        name="Incremental processing",
        criterion_type=CriterionType.BINARY,
        services=["delta_live_tables", "structured_streaming"],
        description="DLT or Structured Streaming used for incremental rather than full recompute",
    ),
    CriterionDefinition(
        pillar="P7", index=6,
        name="Pipelines with scheduled refresh",
        criterion_type=CriterionType.ANALOG,
        services=["databricks_workflows"],
        description="Percentage of production pipelines with scheduled workflow triggers",
    ),
    CriterionDefinition(
        pillar="P7", index=7,
        name="Pipeline freshness monitored",
        criterion_type=CriterionType.BINARY,
        services=["delta_live_tables", "databricks_workflows"],
        description="Pipeline run delays and data staleness actively monitored with alerts",
    ),
    CriterionDefinition(
        pillar="P7", index=8,
        name="Delta Lake versioning active",
        criterion_type=CriterionType.ANALOG,
        services=["delta_lake"],
        description="Percentage of tables with Delta history retention enabling point-in-time queries",
    ),
    CriterionDefinition(
        pillar="P7", index=9,
        name="Auto Loader ingestion",
        criterion_type=CriterionType.BINARY,
        services=["structured_streaming", "delta_lake"],
        description="Auto Loader (cloudFiles) used for automatic file ingestion into Delta Lake",
    ),
]


# ---------------------------------------------------------------------------
# Combined registry: all Databricks criteria in pillar order
# ---------------------------------------------------------------------------
DATABRICKS_CRITERIA_REGISTRY: list[CriterionDefinition] = (
    _P1_CRITERIA
    + _P3_CRITERIA
    + _P4_CRITERIA
    + _P5_CRITERIA
    + _P6_CRITERIA
    + _P7_CRITERIA
)


# ---------------------------------------------------------------------------
# Convenience lookups
# ---------------------------------------------------------------------------

#: Applicable pillars for Databricks platform
DATABRICKS_PILLARS: list[str] = ["P1", "P3", "P4", "P5", "P6", "P7"]

#: Pillar display names for Databricks-applicable pillars
DATABRICKS_PILLAR_NAMES: dict[str, str] = {
    "P1": "Agent Access & Discovery",
    "P3": "Data Lineage & Provenance",
    "P4": "Data Quality, Contracts & Classification",
    "P5": "Access Control, Identity & Tenancy",
    "P6": "Observability & Audit",
    "P7": "Real-Time, Freshness & Zero-ETL",
}

#: Expected criterion counts per pillar for Databricks
DATABRICKS_PILLAR_CRITERIA_COUNTS: dict[str, int] = {
    "P1": len(_P1_CRITERIA),
    "P3": len(_P3_CRITERIA),
    "P4": len(_P4_CRITERIA),
    "P5": len(_P5_CRITERIA),
    "P6": len(_P6_CRITERIA),
    "P7": len(_P7_CRITERIA),
}


def get_databricks_criteria_for_pillar(pillar: str) -> list[CriterionDefinition]:
    """Return all Databricks criteria belonging to a specific pillar code (e.g., 'P1').

    Args:
        pillar: Pillar code string (e.g., "P1", "P3", "P4", "P5", "P6", "P7").

    Returns:
        List of CriterionDefinition objects for the given pillar.
        Empty list if pillar has no Databricks criteria.
    """
    return [c for c in DATABRICKS_CRITERIA_REGISTRY if c.pillar == pillar]


def get_databricks_criterion(pillar: str, index: int) -> CriterionDefinition | None:
    """Look up a single Databricks criterion by pillar and index.

    Args:
        pillar: Pillar code string (e.g., "P1").
        index: Criterion index within the pillar (1-based).

    Returns:
        The matching CriterionDefinition, or None if not found.
    """
    for c in DATABRICKS_CRITERIA_REGISTRY:
        if c.pillar == pillar and c.index == index:
            return c
    return None


def get_all_databricks_services() -> set[str]:
    """Return the set of all unique Databricks service keys referenced across all criteria."""
    services: set[str] = set()
    for c in DATABRICKS_CRITERIA_REGISTRY:
        services.update(c.services)
    return services

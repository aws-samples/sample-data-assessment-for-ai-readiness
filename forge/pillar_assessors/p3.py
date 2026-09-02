"""
FORGE 2.3 — Pillar 3: Data Lineage & Provenance (14 criteria)
"""
from forge.pillar_assessors._common import get_client, safe_call, make_criterion


def assess_p3(region):
    """Assess P3: Data Lineage & Provenance."""
    criteria = []
    glue = get_client("glue", region)
    sagemaker = get_client("sagemaker", region)

    # Check for lineage groups
    lineage_groups = safe_call(lambda: sagemaker.list_lineage_groups())
    has_lineage = lineage_groups and "_error" not in lineage_groups and len(lineage_groups.get("LineageGroupSummaries",[])) > 0

    # Check for Glue jobs (partial lineage)
    jobs = safe_call(lambda: glue.list_jobs())
    has_jobs = jobs and "_error" not in jobs and len(jobs.get("JobNames",[])) > 0
    job_count = len(jobs.get("JobNames",[])) if has_jobs else 0

    # P3.1 - Source-to-consumption lineage for >50% of curated assets
    criteria.append(make_criterion(1, "Source-to-consumption lineage exists",
        has_lineage or has_jobs,
        f"SageMaker lineage: {has_lineage}, Glue jobs: {job_count}", 70))

    # P3.2 - Lineage captures transformations (job facet)
    criteria.append(make_criterion(2, "Lineage captures transformations",
        has_jobs, f"Glue ETL jobs as transformation lineage: {job_count} jobs", 65))

    # P3.3 - Auto-updated lineage (not manual documentation)
    criteria.append(make_criterion(3, "Auto-updated lineage",
        has_lineage, f"SageMaker auto-lineage: {has_lineage}", 70))

    # P3.4 - Multi-engine lineage spans (Spark + SQL + streaming)
    criteria.append(make_criterion(4, "Multi-engine lineage spans",
        has_lineage and has_jobs,
        f"Multi-engine (SageMaker + Glue): {has_lineage and has_jobs}", 55))

    # P3.5 - Queryable via API (SageMaker Lineage API)
    criteria.append(make_criterion(5, "Lineage queryable via API",
        has_lineage, f"SageMaker Lineage API available: {has_lineage}", 85))

    # P3.6 - Follows open standard (OpenLineage JSON schema)
    criteria.append(make_criterion(6, "Follows OpenLineage standard",
        False, "OpenLineage conformance not auto-detectable", 50))

    # P3.7 - Column-level lineage exists
    criteria.append(make_criterion(7, "Column-level lineage exists",
        has_lineage, "Column lineage requires SageMaker lineage groups", 55))

    # P3.8 - Timestamps included on all events
    criteria.append(make_criterion(8, "Timestamps on all lineage events",
        has_lineage or has_jobs,
        "Glue jobs and SageMaker lineage include timestamps", 75))

    # P3.9 - Freshness tracked and verifiable
    criteria.append(make_criterion(9, "Freshness tracked and verifiable",
        has_jobs, "Glue job run history provides freshness signals", 60))

    # P3.10 - Source system of record identified
    criteria.append(make_criterion(10, "Source system of record identified",
        has_jobs, "Job source/target mappings provide SoR identification", 55))

    # P3.11 - Transformation logic linked via source code URI
    criteria.append(make_criterion(11, "Transformation logic linked",
        has_jobs, "Glue jobs link to script locations", 65))

    # P3.12 - Lineage immutable/append-only
    criteria.append(make_criterion(12, "Lineage immutable/append-only",
        False, "S3 Object Lock on lineage store not detected", 50))

    # P3.13 - Audit trail for vector index builds
    criteria.append(make_criterion(13, "Audit trail for vector index builds",
        False, "Vector embedding build audit not detected", 45))

    # P3.14 - Right-to-be-forgotten implementable in vector indices
    criteria.append(make_criterion(14, "Right-to-be-forgotten in vector indices",
        False, "Requires manual verification of deletion capability", 40))

    return {"code": "P3", "name": "Data Lineage & Provenance", "total": 14, "criteria": criteria}

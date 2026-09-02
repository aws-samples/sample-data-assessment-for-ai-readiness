"""
FORGE 2.3 — Pillar 4: Data Quality, Contracts & Classification (18 criteria)
"""
from forge.pillar_assessors._common import get_client, safe_call, make_criterion


def assess_p4(region):
    """Assess P4: Data Quality, Contracts & Classification."""
    criteria = []
    glue = get_client("glue", region)

    # Check DQ rulesets
    dq_rulesets = safe_call(lambda: glue.list_data_quality_rulesets())
    has_dq = dq_rulesets and "_error" not in dq_rulesets and len(dq_rulesets.get("Rulesets",[])) > 0
    dq_count = len(dq_rulesets.get("Rulesets",[])) if has_dq else 0

    # P4.1 - Quality rules defined for critical datasets
    criteria.append(make_criterion(1, "Quality rules defined for critical datasets",
        has_dq, f"Glue DQ rulesets found: {dq_count}", 85))

    # P4.2 - Completeness checks present
    criteria.append(make_criterion(2, "Completeness checks present in DQ rules",
        has_dq, f"DQ rulesets present (completeness assumed if DQ active): {has_dq}", 60))

    # P4.3 - Uniqueness checks present
    criteria.append(make_criterion(3, "Uniqueness checks present",
        has_dq, f"DQ rulesets present (uniqueness checks assumed): {has_dq}", 60))

    # P4.4 - Freshness/recency checks present
    criteria.append(make_criterion(4, "Freshness/recency checks present",
        has_dq, f"DQ rulesets present (freshness assumed): {has_dq}", 55))

    # P4.5 - Referential integrity checks present
    criteria.append(make_criterion(5, "Referential integrity checks present",
        False, "Referential integrity checks require manual DQDL inspection", 45))

    # P4.6 - Business logic validation rules defined
    criteria.append(make_criterion(6, "Business logic validation rules defined",
        has_dq, "Custom rules in DQDL rulesets", 50))

    # P4.7 - Checks run automatically (EventBridge/trigger)
    events = get_client("events", region)
    rules = safe_call(lambda: events.list_rules(NamePrefix="glue"))
    has_auto_dq = rules and "_error" not in rules and len(rules.get("Rules",[])) > 0
    criteria.append(make_criterion(7, "DQ checks run automatically",
        has_auto_dq or has_dq,
        f"EventBridge DQ triggers: {has_auto_dq}, DQ rulesets: {has_dq}", 65))

    # P4.8 - Quality scores computed and stored
    criteria.append(make_criterion(8, "Quality scores computed and stored",
        has_dq, f"DQ rulesets produce scores: {has_dq}", 70))

    # P4.9 - Scores visible in catalog
    criteria.append(make_criterion(9, "DQ scores visible in catalog",
        has_dq, "Glue DQ scores queryable via API", 60))

    # P4.10 - Alerts on quality drift (EventBridge -> SNS)
    sns = get_client("sns", region)
    topics = safe_call(lambda: sns.list_topics())
    has_sns = topics and "_error" not in topics and len(topics.get("Topics",[])) > 0
    criteria.append(make_criterion(10, "Alerts on quality drift",
        has_dq and has_sns, f"DQ + SNS topics: {has_dq and has_sns}", 55))

    # P4.11 - Certified flag exists on assets
    all_dbs = safe_call(lambda: glue.get_databases())
    certified_found = False
    if all_dbs and "_error" not in all_dbs:
        for db in all_dbs.get("DatabaseList", [])[:5]:
            tbls = safe_call(lambda: glue.get_tables(DatabaseName=db["Name"]))
            if tbls and "_error" not in tbls:
                for t in tbls.get("TableList", []):
                    params = t.get("Parameters", {})
                    if "certified" in str(params).lower() or "quality_score" in str(params).lower():
                        certified_found = True
                        break
    criteria.append(make_criterion(11, "Certified flag exists on assets",
        certified_found, f"Certification metadata: {certified_found}", 60))

    # P4.12 - Certification based on score threshold
    criteria.append(make_criterion(12, "Certification based on score threshold",
        certified_found, "Requires threshold-based cert logic", 45))

    # P4.13 - Agents can check certification status programmatically
    criteria.append(make_criterion(13, "Agents can check certification via API",
        certified_found, "Glue API exposes table parameters", 65))

    # P4.14 - Automated PII/PHI/PCI detection (Macie)
    macie = get_client("macie2", region)
    macie_status = safe_call(lambda: macie.get_macie_session())
    has_macie = macie_status and "_error" not in macie_status and macie_status.get("status") == "ENABLED"
    criteria.append(make_criterion(14, "Automated PII/PHI/PCI detection (Macie)",
        has_macie, f"Macie enabled: {has_macie}", 90))

    # P4.15 - Sensitivity labels auto-applied
    criteria.append(make_criterion(15, "Sensitivity labels auto-applied in catalog",
        has_macie, f"Macie -> catalog labels: {has_macie}", 65))

    # P4.16 - Schema contracts exist (Glue Schema Registry)
    schema_reg = safe_call(lambda: glue.list_registries())
    has_registry = schema_reg and "_error" not in schema_reg and len(schema_reg.get("Registries",[])) > 0
    criteria.append(make_criterion(16, "Schema contracts exist (Schema Registry)",
        has_registry, f"Glue Schema Registry: {has_registry}", 80))

    # P4.17 - Breaking changes detected and alerted
    criteria.append(make_criterion(17, "Breaking changes detected and alerted",
        has_registry, "Schema Registry provides compatibility checks", 60))

    # P4.18 - ML model outputs have trust scores (SageMaker Model Monitor)
    sm = get_client("sagemaker", region)
    monitors = safe_call(lambda: sm.list_monitoring_schedules())
    has_monitor = monitors and "_error" not in monitors and len(monitors.get("MonitoringScheduleSummaries",[])) > 0
    criteria.append(make_criterion(18, "ML model outputs have trust scores",
        has_monitor, f"SageMaker Model Monitor: {has_monitor}", 75))

    return {"code": "P4", "name": "Data Quality, Contracts & Classification", "total": 18, "criteria": criteria}

"""
FORGE 2.3 — Pillar 6: Observability & Audit (12 criteria)
"""
from forge.pillar_assessors._common import get_client, safe_call, make_criterion


def assess_p6(region):
    """Assess P6: Observability & Audit."""
    criteria = []
    ct = get_client("cloudtrail", region)
    cw = get_client("cloudwatch", region)
    logs = get_client("logs", region)

    # Check CloudTrail
    trails = safe_call(lambda: ct.describe_trails())
    has_trail = trails and "_error" not in trails and len(trails.get("trailList",[])) > 0

    # Check data events
    data_events_enabled = False
    if has_trail:
        for trail in trails.get("trailList", []):
            selectors = safe_call(lambda: ct.get_event_selectors(TrailName=trail["Name"]))
            if selectors and "_error" not in selectors:
                adv = selectors.get("AdvancedEventSelectors", [])
                basic = selectors.get("EventSelectors", [])
                if adv or any(es.get("IncludeManagementEvents") for es in basic):
                    for sel in basic:
                        if sel.get("DataResources"):
                            data_events_enabled = True
                    if "S3" in str(adv) or "Glue" in str(adv):
                        data_events_enabled = True

    # P6.1 - Agent-to-data interactions logged (CloudTrail data events)
    criteria.append(make_criterion(1, "Agent-to-data interactions logged",
        data_events_enabled, f"CloudTrail data events: {data_events_enabled}", 90))

    # P6.2 - Intent context included in logs
    criteria.append(make_criterion(2, "Intent context in logs (user-agent/metadata)",
        False, "Intent context in request metadata requires manual check", 45))

    # P6.3 - Distributed tracing (OTEL or X-Ray)
    xray_groups = safe_call(lambda: get_client("xray", region).get_groups())
    has_xray = xray_groups and "_error" not in xray_groups
    otel_logs = safe_call(lambda: logs.describe_log_groups(logGroupNamePrefix="/aws/xray"))
    has_otel = otel_logs and "_error" not in otel_logs and len(otel_logs.get("logGroups",[])) > 0
    criteria.append(make_criterion(3, "Distributed tracing (OTEL/X-Ray)",
        has_xray or has_otel, f"X-Ray: {has_xray}, OTEL logs: {has_otel}", 80))

    # P6.4 - Traces follow open standard (OTEL exporter)
    criteria.append(make_criterion(4, "Traces follow open standard (OTEL)",
        has_otel, f"OTEL log groups: {has_otel}", 65))

    # P6.5 - Per-agent cost measurable (cost allocation tags)
    criteria.append(make_criterion(5, "Per-agent cost measurable",
        False, "Cost allocation tags on agent resources not verified", 45))

    # P6.6 - Per-query cost attributable (Athena workgroup/Redshift logging)
    athena = get_client("athena", region)
    wgs = safe_call(lambda: athena.list_work_groups())
    has_wgs = wgs and "_error" not in wgs and len(wgs.get("WorkGroups",[])) > 1
    criteria.append(make_criterion(6, "Per-query cost attributable",
        has_wgs, f"Athena workgroups for cost separation: {has_wgs}", 70))

    # P6.7 - Cost anomaly detection active
    ce = get_client("ce", "us-east-1")
    anomalies = safe_call(lambda: ce.get_anomaly_monitors())
    has_anomaly = anomalies and "_error" not in anomalies and len(anomalies.get("AnomalyMonitors",[])) > 0
    criteria.append(make_criterion(7, "Cost anomaly detection active",
        has_anomaly, f"Cost anomaly monitors: {has_anomaly}", 85))

    # P6.8 - Audit queryable with SQL (<5 min answer time)
    criteria.append(make_criterion(8, "Audit queryable with SQL",
        has_trail and has_wgs,
        f"CloudTrail + Athena workgroups: {has_trail and has_wgs}", 65))

    # P6.9 - Machine access logged (not just humans)
    criteria.append(make_criterion(9, "Machine access logged",
        has_trail, "CloudTrail captures all API calls including machine identity", 80))

    # P6.10 - Logs cover data-layer access
    criteria.append(make_criterion(10, "Logs cover data-layer access",
        data_events_enabled, f"Data events enabled: {data_events_enabled}", 85))

    # P6.11 - Audit Manager / Config rules active
    config = get_client("config", region)
    config_rules = safe_call(lambda: config.describe_config_rules())
    has_config = config_rules and "_error" not in config_rules and len(config_rules.get("ConfigRules",[])) > 0
    criteria.append(make_criterion(11, "AWS Config / Audit Manager active",
        has_config, f"Config rules: {has_config}", 80))

    # P6.12 - Regulatory evidence packs producible
    criteria.append(make_criterion(12, "Regulatory evidence packs producible",
        has_config and has_trail,
        f"Config + CloudTrail for evidence: {has_config and has_trail}", 60))

    return {"code": "P6", "name": "Observability & Audit", "total": 12, "criteria": criteria}

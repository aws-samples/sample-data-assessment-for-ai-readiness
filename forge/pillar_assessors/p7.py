"""
FORGE 2.3 — Pillar 7: Real-Time, Freshness & Zero-ETL (15 criteria)
"""
from forge.pillar_assessors._common import get_client, safe_call, make_criterion


def assess_p7(region):
    """Assess P7: Real-Time, Freshness & Zero-ETL."""
    criteria = []
    glue = get_client("glue", region)

    # Check streaming services
    kinesis = get_client("kinesis", region)
    streams = safe_call(lambda: kinesis.list_streams())
    has_kinesis = streams and "_error" not in streams and len(streams.get("StreamNames",[])) > 0

    msk = get_client("kafka", region)
    clusters = safe_call(lambda: msk.list_clusters_v2())
    has_msk = clusters and "_error" not in clusters and len(clusters.get("ClusterInfoList",[])) > 0

    has_streaming = has_kinesis or has_msk

    # Check for Glue table freshness metadata
    all_dbs = safe_call(lambda: glue.get_databases())
    tables_with_freshness = 0
    total_tables = 0
    if all_dbs and "_error" not in all_dbs:
        for db in all_dbs.get("DatabaseList", [])[:5]:
            tbls = safe_call(lambda: glue.get_tables(DatabaseName=db["Name"]))
            if tbls and "_error" not in tbls:
                for t in tbls.get("TableList", []):
                    total_tables += 1
                    params = t.get("Parameters", {})
                    if any(k in str(params).lower() for k in ["freshness", "last_updated", "update_frequency"]):
                        tables_with_freshness += 1

    # P7.1 - At least one dataset updated real-time (<5 min lag)
    criteria.append(make_criterion(1, "Real-time dataset exists (<5 min lag)",
        has_streaming, f"Kinesis: {has_kinesis}, MSK: {has_msk}", 80))

    # P7.2 - Freshness SLAs defined
    criteria.append(make_criterion(2, "Freshness SLAs defined in metadata",
        tables_with_freshness > 0,
        f"{tables_with_freshness}/{total_tables} tables with freshness metadata", 65))

    # P7.3 - Freshness measurable/queryable via API
    criteria.append(make_criterion(3, "Freshness measurable/queryable via API",
        total_tables > 0,
        "Glue table UpdateTime provides basic freshness", 60))

    # P7.4 - Agents can verify freshness before use
    criteria.append(make_criterion(4, "Agents can verify freshness before use",
        tables_with_freshness > 0,
        f"Freshness metadata queryable: {tables_with_freshness > 0}", 55))

    # P7.5 - Streaming ingestion layer exists
    criteria.append(make_criterion(5, "Streaming ingestion layer exists",
        has_streaming, f"Kinesis/MSK present: {has_streaming}", 85))

    # P7.6 - Streaming sink writes to governed cataloged storage
    criteria.append(make_criterion(6, "Streaming to governed cataloged storage",
        has_streaming and total_tables > 0,
        "Streaming + Glue catalog present", 60))

    # P7.7 - Streaming pipelines emit lineage
    criteria.append(make_criterion(7, "Streaming pipelines emit lineage",
        False, "Streaming lineage emission not auto-detected", 45))

    # P7.8 - Streaming destinations have DQ enforcement
    dq = safe_call(lambda: glue.list_data_quality_rulesets())
    has_dq = dq and "_error" not in dq and len(dq.get("Rulesets",[])) > 0
    criteria.append(make_criterion(8, "Streaming destinations have DQ rules",
        has_dq and has_streaming,
        f"DQ + streaming: {has_dq and has_streaming}", 55))

    # P7.9 - Schema changes detected and alerted
    schema_reg = safe_call(lambda: glue.list_registries())
    has_registry = schema_reg and "_error" not in schema_reg and len(schema_reg.get("Registries",[])) > 0
    criteria.append(make_criterion(9, "Schema changes detected and alerted",
        has_registry, f"Glue Schema Registry: {has_registry}", 70))

    # P7.10 - Data drift monitored
    criteria.append(make_criterion(10, "Data drift monitored",
        has_dq, f"DQ rules for drift detection: {has_dq}", 60))

    # P7.11 - Time-travel supported (Iceberg/Delta)
    open_format = False
    if all_dbs and "_error" not in all_dbs:
        for db in all_dbs.get("DatabaseList", [])[:5]:
            tbls = safe_call(lambda: glue.get_tables(DatabaseName=db["Name"]))
            if tbls and "_error" not in tbls:
                for t in tbls.get("TableList", []):
                    if "iceberg" in str(t.get("Parameters",{})).lower():
                        open_format = True
                        break
            if open_format:
                break
    criteria.append(make_criterion(11, "Time-travel supported (Iceberg/Delta)",
        open_format, f"Iceberg tables: {open_format}", 80))

    # P7.12 - Change notifications routed to agents (EventBridge)
    events = get_client("events", region)
    eb_rules = safe_call(lambda: events.list_rules())
    has_eb = eb_rules and "_error" not in eb_rules and len(eb_rules.get("Rules",[])) > 0
    criteria.append(make_criterion(12, "Change notifications routed to agents",
        has_eb, f"EventBridge rules: {has_eb}", 60))

    # P7.13 - Zero-ETL replication exists
    rds = get_client("rds", region)
    integrations = safe_call(lambda: rds.describe_integrations())
    has_zero_etl = integrations and "_error" not in integrations and len(integrations.get("Integrations",[])) > 0
    criteria.append(make_criterion(13, "Zero-ETL replication exists",
        has_zero_etl, f"Zero-ETL integrations: {has_zero_etl}", 85))

    # P7.14 - Zero-ETL destinations governed (LF policies apply)
    lf = get_client("lakeformation", region)
    lf_active = safe_call(lambda: lf.get_data_lake_settings())
    has_lf = lf_active and "_error" not in lf_active
    criteria.append(make_criterion(14, "Zero-ETL destinations governed",
        has_zero_etl and has_lf,
        f"Zero-ETL + Lake Formation: {has_zero_etl and has_lf}", 65))

    # P7.15 - Vector embeddings refreshed on defined schedule
    bedrock = get_client("bedrock-agent", region)
    kbs = safe_call(lambda: bedrock.list_knowledge_bases())
    has_kb = kbs and "_error" not in kbs and len(kbs.get("knowledgeBaseSummaries",[])) > 0
    criteria.append(make_criterion(15, "Vector embeddings refreshed on schedule",
        has_kb, f"Bedrock KB (embedding refresh): {has_kb}", 55))

    return {"code": "P7", "name": "Real-Time, Freshness & Zero-ETL", "total": 15, "criteria": criteria}

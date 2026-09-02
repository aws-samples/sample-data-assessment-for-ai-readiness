"""
FORGE 2.3 — Pillar 1: Agent Access & Discovery (21 criteria)
"""
from forge.pillar_assessors._common import get_client, safe_call, make_criterion


def assess_p1(region):
    """Assess P1: Agent Access & Discovery."""
    criteria = []
    glue = get_client("glue", region)
    cfn = get_client("cloudformation", region)
    iam = get_client("iam", region)
    s3 = get_client("s3", region)
    lf = get_client("lakeformation", region)

    # P1.1 - API queryable without human approval
    result = safe_call(lambda: glue.get_databases(MaxResults=1))
    if result and "_error" not in result:
        criteria.append(make_criterion(1, "API queryable without human approval", True,
            f"GetDatabases API succeeded. Found databases.", 95))
    else:
        criteria.append(make_criterion(1, "API queryable without human approval", False,
            f"GetDatabases failed: {result.get('_error','unknown')}", 90))

    # P1.2 - Catalog REST API exists (Iceberg REST or equivalent)
    stacks = safe_call(lambda: cfn.list_stacks(
        StackStatusFilter=["CREATE_COMPLETE", "UPDATE_COMPLETE"]))
    iceberg_found = False
    if stacks and "_error" not in stacks:
        iceberg_stacks = [s for s in stacks.get("StackSummaries", [])
                         if "iceberg" in s.get("StackName", "").lower()
                         or "rest-catalog" in s.get("StackName", "").lower()
                         or "s3tables" in s.get("StackName", "").lower()]
        iceberg_found = len(iceberg_stacks) > 0
    criteria.append(make_criterion(2, "Catalog REST API exists", iceberg_found,
        f"Iceberg/REST stacks found: {iceberg_found}", 70))

    # P1.3 - Schema introspection available programmatically
    tables_result = safe_call(lambda: glue.get_databases(MaxResults=5))
    schema_ok = False
    if tables_result and "_error" not in tables_result:
        for db in tables_result.get("DatabaseList", [])[:3]:
            tbl = safe_call(lambda: glue.get_tables(DatabaseName=db["Name"], MaxResults=1))
            if tbl and "_error" not in tbl and tbl.get("TableList"):
                schema_ok = True
                break
    criteria.append(make_criterion(3, "Schema introspection available programmatically",
        schema_ok, f"GetTables with schema info available: {schema_ok}", 90))

    # P1.4 - MCP server or tool interface exists
    lambdas = safe_call(lambda: get_client("lambda", region).list_functions(MaxItems=50))
    mcp_found = False
    if lambdas and "_error" not in lambdas:
        mcp_found = any("mcp" in f.get("FunctionName","").lower() or
                       "agentcore" in f.get("FunctionName","").lower() or
                       "tool-server" in f.get("FunctionName","").lower()
                       for f in lambdas.get("Functions", []))
    criteria.append(make_criterion(4, "MCP server or tool interface exists", mcp_found,
        f"MCP/AgentCore Lambda functions found: {mcp_found}", 70))

    # P1.5 - Auth supports machine identity (IAM roles)
    roles = safe_call(lambda: iam.list_roles(MaxItems=100))
    agent_roles = []
    if roles and "_error" not in roles:
        agent_roles = [r for r in roles.get("Roles", [])
                      if any(kw in r.get("RoleName","").lower()
                            for kw in ["agent", "machine", "service", "bedrock", "sagemaker"])]
    criteria.append(make_criterion(5, "Auth supports machine identity (IAM roles)",
        len(agent_roles) > 0,
        f"Found {len(agent_roles)} machine/agent IAM roles", 85))

    # P1.6 - Searchable catalog covers >80% of production data assets
    all_dbs = safe_call(lambda: glue.get_databases())
    total_tables = 0
    if all_dbs and "_error" not in all_dbs:
        for db in all_dbs.get("DatabaseList", []):
            tbls = safe_call(lambda: glue.get_tables(DatabaseName=db["Name"]))
            if tbls and "_error" not in tbls:
                total_tables += len(tbls.get("TableList", []))
    criteria.append(make_criterion(6, "Searchable catalog covers >80% of production assets",
        total_tables >= 10,
        f"Found {total_tables} tables in Glue catalog", 60))

    # P1.7 - Catalog entries have human-readable descriptions (>80%)
    tables_with_desc = 0
    tables_checked = 0
    if all_dbs and "_error" not in all_dbs:
        for db in all_dbs.get("DatabaseList", [])[:5]:
            tbls = safe_call(lambda: glue.get_tables(DatabaseName=db["Name"]))
            if tbls and "_error" not in tbls:
                for t in tbls.get("TableList", []):
                    tables_checked += 1
                    if t.get("Description") and len(t["Description"]) > 10:
                        tables_with_desc += 1
    desc_pct = (tables_with_desc / max(tables_checked, 1)) * 100
    criteria.append(make_criterion(7, "Catalog entries have human-readable descriptions (>80%)",
        desc_pct >= 80,
        f"{tables_with_desc}/{tables_checked} tables have descriptions ({desc_pct:.0f}%)", 75))

    # P1.8 - Data organized into domains/namespaces (not flat "default")
    db_names = []
    if all_dbs and "_error" not in all_dbs:
        db_names = [db["Name"] for db in all_dbs.get("DatabaseList", [])]
    non_default = [n for n in db_names if n != "default"]
    criteria.append(make_criterion(8, "Data organized into domains/namespaces",
        len(non_default) >= 2,
        f"Databases: {db_names[:10]}. Non-default: {len(non_default)}", 80))

    # P1.9 - Cross-engine discovery (same asset findable from any engine)
    athena = get_client("athena", region)
    wgs = safe_call(lambda: athena.list_work_groups())
    cross_engine = False
    if wgs and "_error" not in wgs:
        cross_engine = len(wgs.get("WorkGroups", [])) > 1
    criteria.append(make_criterion(9, "Cross-engine discovery",
        cross_engine, f"Athena workgroups found: {cross_engine}", 65))

    # P1.10 - Catalog metadata auto-refreshed (<24h)
    crawlers = safe_call(lambda: glue.get_crawlers())
    crawler_active = False
    if crawlers and "_error" not in crawlers:
        crawler_active = len(crawlers.get("Crawlers", [])) > 0
    criteria.append(make_criterion(10, "Catalog metadata auto-refreshed",
        crawler_active, f"Glue crawlers found: {crawler_active}", 75))

    # P1.11 - Open table format used (Iceberg/Delta/Hudi)
    open_format = False
    if all_dbs and "_error" not in all_dbs:
        for db in all_dbs.get("DatabaseList", [])[:5]:
            tbls = safe_call(lambda: glue.get_tables(DatabaseName=db["Name"]))
            if tbls and "_error" not in tbls:
                for t in tbls.get("TableList", []):
                    params = t.get("Parameters", {})
                    if any(k in str(params).lower() for k in ["iceberg", "delta", "hudi"]):
                        open_format = True
                        break
            if open_format:
                break
    criteria.append(make_criterion(11, "Open table format (Iceberg/Delta/Hudi)",
        open_format, f"Open format tables detected: {open_format}", 85))

    # P1.12 - Storage layer separated from compute
    criteria.append(make_criterion(12, "Storage separated from compute",
        True, "S3-based architecture assumed (Glue catalog implies S3 storage)", 70))

    # P1.13 - Zero-copy read path available
    lf_resources = safe_call(lambda: lf.list_resources())
    has_lf = lf_resources and "_error" not in lf_resources and len(lf_resources.get("ResourceInfoList",[])) > 0
    criteria.append(make_criterion(13, "Zero-copy read path available",
        has_lf, f"Lake Formation resources: {has_lf}", 65))

    # P1.14 - Multi-engine access (Athena + Redshift + EMR on same catalog)
    redshift = get_client("redshift", region)
    clusters = safe_call(lambda: redshift.describe_clusters())
    has_redshift = clusters and "_error" not in clusters and len(clusters.get("Clusters",[])) > 0
    multi_engine = cross_engine and has_redshift
    criteria.append(make_criterion(14, "Multi-engine access to same catalog",
        multi_engine, f"Athena+Redshift both present: {multi_engine}", 70))

    # P1.15 - Catalog supports versioning/history
    criteria.append(make_criterion(15, "Catalog supports versioning/history",
        open_format, "Iceberg tables provide version history natively", 60))

    # P1.16 - Relational DBs accessible via governed connection pools
    rds = get_client("rds", region)
    rds_instances = safe_call(lambda: rds.describe_db_instances())
    has_rds = rds_instances and "_error" not in rds_instances and len(rds_instances.get("DBInstances",[])) > 0
    criteria.append(make_criterion(16, "Relational DBs accessible via governed connections",
        has_rds, f"RDS instances found: {has_rds}", 65))

    # P1.17 - NoSQL/document stores have agent-accessible query interfaces
    dynamodb = get_client("dynamodb", region)
    ddb_tables = safe_call(lambda: dynamodb.list_tables())
    has_ddb = ddb_tables and "_error" not in ddb_tables and len(ddb_tables.get("TableNames",[])) > 0
    criteria.append(make_criterion(17, "NoSQL stores have agent-accessible interfaces",
        has_ddb, f"DynamoDB tables found: {has_ddb}", 65))

    # P1.18 - Unstructured data has document-level metadata
    buckets = safe_call(lambda: s3.list_buckets())
    criteria.append(make_criterion(18, "Unstructured data has document-level metadata",
        False, "Requires manual verification of S3 object metadata", 40))

    # P1.19 - Federated query capability exists
    fed_result = safe_call(lambda: athena.list_data_catalogs())
    has_federation = fed_result and "_error" not in fed_result and len(fed_result.get("DataCatalogsSummary",[])) > 1
    criteria.append(make_criterion(19, "Federated query capability exists",
        has_federation or has_redshift,
        f"Athena federation or Redshift Spectrum: {has_federation or has_redshift}", 75))

    # P1.20 - Operational DB queryable cross-boundary
    criteria.append(make_criterion(20, "Operational DB queryable cross-boundary",
        has_federation and has_rds,
        f"Federation + RDS present: {has_federation and has_rds}", 60))

    # P1.21 - Governance applies to federated queries
    lf_settings = safe_call(lambda: lf.get_data_lake_settings())
    lf_active = lf_settings and "_error" not in lf_settings
    criteria.append(make_criterion(21, "Governance applies to federated queries",
        lf_active and has_federation,
        f"Lake Formation active + federation: {lf_active and has_federation}", 65))

    return {"code": "P1", "name": "Agent Access & Discovery", "total": 21, "criteria": criteria}

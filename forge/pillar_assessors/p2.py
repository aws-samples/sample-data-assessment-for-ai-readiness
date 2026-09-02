"""
FORGE 2.3 — Pillar 2: Semantic Context & Retrieval (17 criteria)
"""
from forge.pillar_assessors._common import get_client, safe_call, make_criterion


def assess_p2(region):
    """Assess P2: Semantic Context & Retrieval."""
    criteria = []
    glue = get_client("glue", region)

    # Get all tables for metadata checks
    all_dbs = safe_call(lambda: glue.get_databases())
    all_tables = []
    if all_dbs and "_error" not in all_dbs:
        for db in all_dbs.get("DatabaseList", [])[:10]:
            tbls = safe_call(lambda: glue.get_tables(DatabaseName=db["Name"]))
            if tbls and "_error" not in tbls:
                all_tables.extend(tbls.get("TableList", []))

    # P2.1 - Business glossary exists with defined terms
    has_glossary = any("glossary" in str(t.get("Parameters",{})).lower() or
                      "business_term" in str(t.get("Parameters",{})).lower()
                      for t in all_tables)
    criteria.append(make_criterion(1, "Business glossary exists with defined terms",
        has_glossary, f"Glossary metadata in tables: {has_glossary}", 60))

    # P2.2 - Terms linked to specific tables/columns
    criteria.append(make_criterion(2, "Terms linked to specific tables/columns",
        has_glossary, f"Linked glossary terms: {has_glossary}", 55))

    # P2.3 - Glossary covers >50% of business-critical assets
    criteria.append(make_criterion(3, "Glossary covers >50% of critical assets",
        has_glossary, "Requires manual assessment of glossary coverage", 40))

    # P2.4 - Glossary maintained (last update <90 days)
    criteria.append(make_criterion(4, "Glossary maintained (updated <90 days)",
        has_glossary, "Requires manual verification", 40))

    # P2.5 - Entity relationships formally defined
    neptune = get_client("neptune", region)
    neptune_clusters = safe_call(lambda: neptune.describe_db_clusters())
    has_neptune = neptune_clusters and "_error" not in neptune_clusters and len(neptune_clusters.get("DBClusters",[])) > 0
    criteria.append(make_criterion(5, "Entity relationships formally defined",
        has_neptune, f"Neptune graph DB: {has_neptune}", 70))

    # P2.6 - Hierarchical relationships modeled
    criteria.append(make_criterion(6, "Hierarchical relationships modeled",
        has_neptune, f"Graph DB for hierarchy: {has_neptune}", 60))

    # P2.7 - Synonym/alias mapping exists
    criteria.append(make_criterion(7, "Synonym/alias mapping exists",
        False, "No synonym mapping detected in catalog metadata", 50))

    # P2.8 - Relationships queryable programmatically (openCypher/SPARQL)
    criteria.append(make_criterion(8, "Relationships queryable via openCypher/SPARQL",
        has_neptune, f"Neptune (openCypher support): {has_neptune}", 75))

    # P2.9 - Column-level descriptions for >50% of critical columns
    cols_with_desc = 0
    total_cols = 0
    for t in all_tables[:20]:
        for col in t.get("StorageDescriptor", {}).get("Columns", []):
            total_cols += 1
            if col.get("Comment") and len(col["Comment"]) > 5:
                cols_with_desc += 1
    col_pct = (cols_with_desc / max(total_cols, 1)) * 100
    criteria.append(make_criterion(9, "Column-level descriptions >50% of critical columns",
        col_pct >= 50,
        f"{cols_with_desc}/{total_cols} columns have descriptions ({col_pct:.0f}%)", 75))

    # P2.10 - Data domains defined
    db_names = [db["Name"] for db in all_dbs.get("DatabaseList",[])] if all_dbs and "_error" not in all_dbs else []
    has_domains = len([n for n in db_names if n != "default"]) >= 2
    criteria.append(make_criterion(10, "Data domains defined",
        has_domains, f"Distinct databases as domains: {db_names[:10]}", 70))

    # P2.11 - Data ownership assigned per domain
    criteria.append(make_criterion(11, "Data ownership assigned per domain",
        False, "Requires manual verification of ownership metadata", 40))

    # P2.12 - Business context accessible to agents via API
    criteria.append(make_criterion(12, "Business context accessible via API",
        len(all_tables) > 0,
        f"Glue catalog API accessible with {len(all_tables)} tables", 65))

    # P2.13 - Vector embeddings exist for catalog metadata
    bedrock = get_client("bedrock-agent", region)
    kbs = safe_call(lambda: bedrock.list_knowledge_bases())
    has_kb = kbs and "_error" not in kbs and len(kbs.get("knowledgeBaseSummaries",[])) > 0
    criteria.append(make_criterion(13, "Vector embeddings exist for catalog metadata",
        has_kb, f"Bedrock Knowledge Bases: {has_kb}", 80))

    # P2.14 - Hybrid search available (BM25 + dense vector)
    opensearch = get_client("opensearch", region)
    os_domains = safe_call(lambda: opensearch.list_domain_names())
    has_os = os_domains and "_error" not in os_domains and len(os_domains.get("DomainNames",[])) > 0
    criteria.append(make_criterion(14, "Hybrid search available (BM25 + vector)",
        has_os or has_kb, f"OpenSearch: {has_os}, Bedrock KB: {has_kb}", 70))

    # P2.15 - GraphRAG available
    criteria.append(make_criterion(15, "GraphRAG available (ontology + vector)",
        has_neptune and has_kb,
        f"Neptune + Bedrock KB: {has_neptune and has_kb}", 65))

    # P2.16 - Text-to-SQL retrieval path exists
    criteria.append(make_criterion(16, "Text-to-SQL retrieval path exists",
        has_kb, "Bedrock KB can enable text-to-SQL via agents", 55))

    # P2.17 - Retrieval accuracy evaluated (groundedness tracking)
    criteria.append(make_criterion(17, "Retrieval accuracy evaluated",
        has_kb, "Bedrock KB supports groundedness evaluation", 50))

    return {"code": "P2", "name": "Semantic Context & Retrieval", "total": 17, "criteria": criteria}

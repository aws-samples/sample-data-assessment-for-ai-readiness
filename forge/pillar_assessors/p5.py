"""
FORGE 2.3 — Pillar 5: Access Control, Identity & Tenancy (17 criteria)
"""
from forge.pillar_assessors._common import get_client, safe_call, make_criterion


def assess_p5(region):
    """Assess P5: Access Control, Identity & Tenancy."""
    criteria = []
    lf = get_client("lakeformation", region)
    iam = get_client("iam", region)

    # Check LF settings
    lf_settings = safe_call(lambda: lf.get_data_lake_settings())
    lf_active = lf_settings and "_error" not in lf_settings

    # Check LF permissions
    lf_perms = safe_call(lambda: lf.list_permissions())
    has_perms = lf_perms and "_error" not in lf_perms and len(lf_perms.get("PrincipalResourcePermissions",[])) > 0

    # P5.1 - Column-level access control
    col_perms = False
    if has_perms:
        for p in lf_perms.get("PrincipalResourcePermissions", []):
            resource = p.get("Resource", {})
            if "TableWithColumns" in resource or "ColumnWildcard" in str(resource):
                col_perms = True
                break
    criteria.append(make_criterion(1, "Column-level access control (LF column permissions)",
        col_perms, f"Column-level LF permissions: {col_perms}", 85))

    # P5.2 - Row-level filtering (LF data filters or RLS)
    criteria.append(make_criterion(2, "Row-level filtering",
        False, "Row-level security requires LF data filter inspection", 55))

    # P5.3 - Dynamic data masking
    criteria.append(make_criterion(3, "Dynamic data masking",
        False, "Cell-level masking not auto-detected", 50))

    # P5.4 - Tag-based / attribute-based policies (LF-TBAC)
    lf_tags = safe_call(lambda: lf.list_lf_tags())
    has_tbac = lf_tags and "_error" not in lf_tags and len(lf_tags.get("LFTags",[])) > 0
    criteria.append(make_criterion(4, "Tag-based/attribute-based policies (LF-TBAC)",
        has_tbac, f"LF tags defined: {has_tbac}", 85))

    # P5.5 - Agents have distinct IAM identities
    roles = safe_call(lambda: iam.list_roles(MaxItems=100))
    agent_roles = []
    if roles and "_error" not in roles:
        agent_roles = [r for r in roles.get("Roles",[])
                      if any(kw in r["RoleName"].lower()
                            for kw in ["agent","bedrock","sagemaker-exec","lambda"])]
    criteria.append(make_criterion(5, "Agents have distinct IAM identities",
        len(agent_roles) >= 2,
        f"Agent-specific roles: {len(agent_roles)}", 80))

    # P5.6 - Agent permissions follow least-privilege
    analyzer = get_client("accessanalyzer", region)
    analyzers = safe_call(lambda: analyzer.list_analyzers())
    has_analyzer = analyzers and "_error" not in analyzers and len(analyzers.get("analyzers",[])) > 0
    criteria.append(make_criterion(6, "Agent permissions follow least-privilege",
        has_analyzer, f"IAM Access Analyzer active: {has_analyzer}", 70))

    # P5.7 - Identity chain traceable (agent -> user -> action via CloudTrail)
    ct = get_client("cloudtrail", region)
    trails = safe_call(lambda: ct.describe_trails())
    has_trail = trails and "_error" not in trails and len(trails.get("trailList",[])) > 0
    criteria.append(make_criterion(7, "Identity chain traceable via CloudTrail",
        has_trail, f"CloudTrail trails active: {has_trail}", 85))

    # P5.8 - Agent access revocable independently
    criteria.append(make_criterion(8, "Agent access revocable independently",
        len(agent_roles) >= 2,
        "Separate agent roles enable independent revocation", 70))

    # P5.9 - Policies defined as code (CloudFormation/CDK)
    cfn = get_client("cloudformation", region)
    stacks = safe_call(lambda: cfn.list_stacks(StackStatusFilter=["CREATE_COMPLETE","UPDATE_COMPLETE"]))
    has_iac = stacks and "_error" not in stacks and len(stacks.get("StackSummaries",[])) > 0
    criteria.append(make_criterion(9, "Policies defined as code (IaC)",
        has_iac, f"CloudFormation stacks: {has_iac}", 70))

    # P5.10 - Policies version-controlled
    criteria.append(make_criterion(10, "Policies version-controlled",
        has_iac, "IaC implies version control", 55))

    # P5.11 - Policy evaluation auditable (LF GetEffectivePermissions)
    criteria.append(make_criterion(11, "Policy evaluation auditable",
        lf_active, f"Lake Formation active for policy audit: {lf_active}", 70))

    # P5.12 - Cross-account access governed
    criteria.append(make_criterion(12, "Cross-account access governed",
        has_trail, "CloudTrail logs cross-account access", 60))

    # P5.13 - Policy-based access via Cedar or OPA
    criteria.append(make_criterion(13, "Policy-based access via Cedar/OPA",
        False, "Cedar/OPA policy engine not auto-detected", 50))

    # P5.14 - Policies evaluate at request time per-invocation
    criteria.append(make_criterion(14, "Policies evaluate at request time",
        has_tbac or lf_active,
        f"LF TBAC evaluates at query time: {has_tbac}", 65))

    # P5.15 - Data foundation accepts agent identity at protocol level
    criteria.append(make_criterion(15, "Data foundation accepts agent identity",
        lf_active and len(agent_roles) > 0,
        f"LF + agent roles: {lf_active and len(agent_roles) > 0}", 60))

    # P5.16 - Multi-tenant isolation enforced
    criteria.append(make_criterion(16, "Multi-tenant isolation enforced",
        has_tbac, f"LF TBAC can enforce tenancy: {has_tbac}", 55))

    # P5.17 - Per-tenant cost attribution exists
    criteria.append(make_criterion(17, "Per-tenant cost attribution exists",
        False, "Cost allocation tags for tenancy not auto-verified", 45))

    return {"code": "P5", "name": "Access Control, Identity & Tenancy", "total": 17, "criteria": criteria}

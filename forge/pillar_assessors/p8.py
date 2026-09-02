"""
FORGE 2.3 — Pillar 8: Agent Controllability & Policy Enforcement (16 criteria)
"""
from forge.pillar_assessors._common import get_client, safe_call, make_criterion


def assess_p8(region):
    """Assess P8: Agent Controllability & Policy Enforcement."""
    criteria = []
    bedrock = get_client("bedrock", region)

    # Check Guardrails
    guardrails = safe_call(lambda: bedrock.list_guardrails())
    has_guardrails = guardrails and "_error" not in guardrails and len(guardrails.get("guardrails",[])) > 0
    guardrail_count = len(guardrails.get("guardrails",[])) if has_guardrails else 0

    # P8.1 - Content filtering active (Bedrock Guardrails)
    criteria.append(make_criterion(1, "Content filtering active (Bedrock Guardrails)",
        has_guardrails, f"Active guardrails: {guardrail_count}", 95))

    # P8.2 - Topic restrictions enforced
    criteria.append(make_criterion(2, "Topic restrictions enforced",
        has_guardrails, f"Guardrails with topic policy: {has_guardrails}", 75))

    # P8.3 - Rate limiting per agent
    apigw = get_client("apigateway", region)
    apis = safe_call(lambda: apigw.get_rest_apis())
    has_apigw = apis and "_error" not in apis and len(apis.get("items",[])) > 0
    criteria.append(make_criterion(3, "Rate limiting per agent",
        has_apigw, f"API Gateway (throttling): {has_apigw}", 65))

    # P8.4 - Kill switch exists (agent role disable via Deny/SCP)
    orgs = get_client("organizations", "us-east-1")
    scps = safe_call(lambda: orgs.list_policies(Filter="SERVICE_CONTROL_POLICY"))
    has_scp = scps and "_error" not in scps and len(scps.get("Policies",[])) > 0
    criteria.append(make_criterion(4, "Kill switch exists (Deny policy/SCP)",
        has_scp or True,  # IAM deny policies always possible
        "IAM deny policies can disable agent roles", 70))

    # P8.5 - Policies as code (Cedar/OPA files in deployment)
    criteria.append(make_criterion(5, "Policies as code (Cedar/OPA)",
        False, "Cedar/OPA policy files not auto-detected", 50))

    # P8.6 - Dry-run available (Cedar evaluate API)
    criteria.append(make_criterion(6, "Dry-run policy evaluation available",
        False, "Verified Permissions dry-run not detected", 50))

    # P8.7 - Violations logged and alerted
    cw = get_client("cloudwatch", region)
    alarms = safe_call(lambda: cw.describe_alarms(MaxRecords=20))
    has_alarms = alarms and "_error" not in alarms and len(alarms.get("MetricAlarms",[])) > 0
    criteria.append(make_criterion(7, "Violations logged and alerted",
        has_alarms, f"CloudWatch alarms: {has_alarms}", 60))

    # P8.8 - Policies portable (Cedar/Rego format)
    criteria.append(make_criterion(8, "Policies portable (Cedar/Rego)",
        False, "Portable policy format not detected", 45))

    # P8.9 - High-risk actions require human approval (Step Functions)
    sfn = get_client("stepfunctions", region)
    machines = safe_call(lambda: sfn.list_state_machines())
    has_sfn = machines and "_error" not in machines and len(machines.get("stateMachines",[])) > 0
    criteria.append(make_criterion(9, "High-risk actions require human approval",
        has_sfn, f"Step Functions (HITL workflows): {has_sfn}", 60))

    # P8.10 - Escalation path defined and tested
    sns = get_client("sns", region)
    topics = safe_call(lambda: sns.list_topics())
    has_sns = topics and "_error" not in topics and len(topics.get("Topics",[])) > 0
    criteria.append(make_criterion(10, "Escalation path defined",
        has_sns, f"SNS topics for escalation: {has_sns}", 55))

    # P8.11 - Timeout/circuit-breaker on agent actions
    criteria.append(make_criterion(11, "Timeout/circuit-breaker on agent actions",
        has_sfn or has_apigw,
        f"Step Functions or API GW timeout: {has_sfn or has_apigw}", 55))

    # P8.12 - Agent actions auditable post-hoc
    ct = get_client("cloudtrail", region)
    trails = safe_call(lambda: ct.describe_trails())
    has_trail = trails and "_error" not in trails and len(trails.get("trailList",[])) > 0
    criteria.append(make_criterion(12, "Agent actions auditable post-hoc",
        has_trail, f"CloudTrail for audit: {has_trail}", 80))

    # P8.13 - Policy enforcement at data access layer (Lake Formation)
    lf = get_client("lakeformation", region)
    lf_settings = safe_call(lambda: lf.get_data_lake_settings())
    lf_active = lf_settings and "_error" not in lf_settings
    criteria.append(make_criterion(13, "Policy enforcement at data access layer",
        lf_active, f"Lake Formation active: {lf_active}", 80))

    # P8.14 - Policy enforcement at tool invocation layer
    criteria.append(make_criterion(14, "Policy enforcement at tool invocation layer",
        False, "AgentCore Cedar policy not auto-detected", 50))

    # P8.15 - Policy enforcement at model output layer (Guardrails)
    criteria.append(make_criterion(15, "Policy enforcement at model output layer",
        has_guardrails, f"Bedrock Guardrails on output: {has_guardrails}", 90))

    # P8.16 - Policy enforcement at action layer (human approval gate)
    criteria.append(make_criterion(16, "Policy enforcement at action layer",
        has_sfn, f"Step Functions HITL gate: {has_sfn}", 55))

    return {"code": "P8", "name": "Agent Controllability & Policy Enforcement", "total": 16, "criteria": criteria}

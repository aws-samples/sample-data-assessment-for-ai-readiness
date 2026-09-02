"""
FORGE 2.3 — Pillar 9: Decision Lineage & Explainability (12 criteria)
"""
from forge.pillar_assessors._common import get_client, safe_call, make_criterion


def assess_p9(region):
    """Assess P9: Decision Lineage & Explainability."""
    criteria = []
    logs = get_client("logs", region)
    bedrock = get_client("bedrock", region)

    # Check for model invocation logging
    invocation_logs = safe_call(lambda: bedrock.get_model_invocation_logging_configuration())
    has_invocation_log = (invocation_logs and "_error" not in invocation_logs and
                         invocation_logs.get("loggingConfig", {}).get("s3Config") is not None)

    # Check for X-Ray / OTEL
    xray_logs = safe_call(lambda: logs.describe_log_groups(logGroupNamePrefix="/aws/bedrock"))
    has_bedrock_logs = xray_logs and "_error" not in xray_logs and len(xray_logs.get("logGroups",[])) > 0

    # P9.1 - Agent reasoning steps recorded (OTEL spans)
    criteria.append(make_criterion(1, "Agent reasoning steps recorded",
        has_invocation_log or has_bedrock_logs,
        f"Invocation logging: {has_invocation_log}, Bedrock logs: {has_bedrock_logs}", 80))

    # P9.2 - Each decision links to data sources consulted
    criteria.append(make_criterion(2, "Decisions link to data sources consulted",
        has_invocation_log,
        "Model invocation logging captures input/output context", 55))

    # P9.3 - Intermediate reasoning preserved (Model Invocation Logging)
    criteria.append(make_criterion(3, "Intermediate reasoning preserved",
        has_invocation_log,
        f"Bedrock Model Invocation Logging: {has_invocation_log}", 80))

    # P9.4 - Decision chain queryable via API
    criteria.append(make_criterion(4, "Decision chain queryable via API",
        has_bedrock_logs,
        f"Bedrock log groups queryable: {has_bedrock_logs}", 65))

    # P9.5 - Full reasoning path reconstructable
    criteria.append(make_criterion(5, "Full reasoning path reconstructable",
        has_invocation_log and has_bedrock_logs,
        "Requires invocation logging + log insights", 55))

    # P9.6 - Data-to-decision attribution
    criteria.append(make_criterion(6, "Data-to-decision attribution",
        False, "End-to-end attribution requires manual verification", 40))

    # P9.7 - Confidence/uncertainty quantified
    criteria.append(make_criterion(7, "Confidence/uncertainty quantified",
        False, "Confidence scoring on agent outputs not detected", 40))

    # P9.8 - Alternative actions logged
    criteria.append(make_criterion(8, "Alternative actions logged",
        False, "Alternative reasoning paths not auto-detectable", 35))

    # P9.9 - Decision outcomes tracked (feedback loop)
    criteria.append(make_criterion(9, "Decision outcomes tracked",
        False, "Feedback loop not auto-detected", 40))

    # P9.10 - Human review possible post-hoc
    criteria.append(make_criterion(10, "Human review possible post-hoc",
        has_invocation_log or has_bedrock_logs,
        "Logs enable post-hoc human review", 60))

    # P9.11 - Decision lineage immutable (S3 Object Lock/WORM)
    criteria.append(make_criterion(11, "Decision lineage immutable (Object Lock)",
        False, "S3 Object Lock on decision logs not verified", 45))

    # P9.12 - Regulatory evidence producible in <10 min
    criteria.append(make_criterion(12, "Regulatory evidence producible <10 min",
        has_bedrock_logs,
        f"Queryable Bedrock logs: {has_bedrock_logs}", 50))

    return {"code": "P9", "name": "Decision Lineage & Explainability", "total": 12, "criteria": criteria}

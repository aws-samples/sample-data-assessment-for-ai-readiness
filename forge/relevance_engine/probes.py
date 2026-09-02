"""
FORGE 2.1 — Relevance Engine: Service Probes

Defines the PROBE_REGISTRY mapping each AWS service to a lightweight
list/describe API call, and provides concurrent probe execution.

All functions are importable without CLI context — no argparse, no sys.exit.
Designed to be called from both the Kiro Skill (interactive) and the
collector orchestrator (non-interactive).
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError
from typing import Optional

from forge.aws_client import create_client, safe_call, is_error, is_access_denied
from forge.models import ProbeResult, ServiceClassification


logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Probe Registry
#
# Maps each service name to (boto3_service_name, api_method, result_key).
# result_key is the response dict key containing the resource list.
# A None result_key means success is determined by a non-error response.
# ---------------------------------------------------------------------------
PROBE_REGISTRY: dict[str, tuple[str, str, str | None]] = {
    # Data & Analytics
    "glue": ("glue", "get_databases", "DatabaseList"),
    "kinesis": ("kinesis", "list_streams", "StreamNames"),
    "msk": ("kafka", "list_clusters_v2", "ClusterInfoList"),
    "s3": ("s3", "list_buckets", "Buckets"),
    "lakeformation": ("lakeformation", "list_resources", "ResourceInfoList"),
    "dynamodb": ("dynamodb", "list_tables", "TableNames"),
    "rds": ("rds", "describe_db_instances", "DBInstances"),
    "redshift": ("redshift", "describe_clusters", "Clusters"),
    "neptune": ("neptune", "describe_db_clusters", "DBClusters"),
    "opensearch": ("opensearch", "list_domain_names", "DomainNames"),
    "athena": ("athena", "list_work_groups", "WorkGroups"),
    # AI/ML
    "bedrock-agent": ("bedrock-agent", "list_knowledge_bases", "knowledgeBaseSummaries"),
    "sagemaker": ("sagemaker", "list_notebook_instances", "NotebookInstances"),
    "bedrock": ("bedrock", "list_foundation_models", "modelSummaries"),
    # Security & Compliance
    "macie2": ("macie2", "get_macie_session", "status"),
    "iam": ("iam", "list_roles", "Roles"),
    "accessanalyzer": ("accessanalyzer", "list_analyzers", "analyzers"),
    # Application Services
    "apigateway": ("apigateway", "get_rest_apis", "items"),
    "appsync": ("appsync", "list_graphql_apis", "graphqlApis"),
    "cognito-idp": ("cognito-idp", "list_user_pools", "UserPools"),
    "lambda": ("lambda", "list_functions", "Functions"),
    "stepfunctions": ("stepfunctions", "list_state_machines", "stateMachines"),
    # Observability & Governance
    "cloudtrail": ("cloudtrail", "describe_trails", "trailList"),
    "config": ("config", "describe_config_rules", "ConfigRules"),
    "cloudwatch": ("cloudwatch", "describe_alarms", "MetricAlarms"),
    "events": ("events", "list_rules", "Rules"),
    "sns": ("sns", "list_topics", "Topics"),
    "xray": ("xray", "get_groups", "Groups"),
    # Cost & Management
    "cost-explorer": ("ce", "get_cost_and_usage", None),
    "cloudformation": ("cloudformation", "list_stacks", "StackSummaries"),
}

# Concurrency settings
MAX_WORKERS = 10
PROBE_TIMEOUT_SECONDS = 60

# Error codes that indicate an access/permission issue (no retry)
_ACCESS_DENIED_CODES = frozenset({
    "AccessDeniedException",
    "AccessDenied",
    "UnauthorizedOperation",
})

# Error codes that indicate transient/endpoint issues (worth retrying)
_RETRYABLE_CODES = frozenset({
    "EndpointConnectionError",
    "ConnectTimeoutError",
    "ReadTimeoutError",
    "ThrottlingException",
    "RequestTimeout",
    "ServiceUnavailable",
    "InternalError",
    "ConnectionError",
})


def _build_call_kwargs(service_name: str, method_name: str) -> dict:
    """Build any special kwargs needed for specific API calls.

    Some APIs require parameters (e.g., cognito-idp list_user_pools needs
    MaxResults, cost-explorer needs TimePeriod).
    """
    from datetime import date, timedelta

    if service_name == "cognito-idp" and method_name == "list_user_pools":
        return {"MaxResults": 10}

    if service_name == "cost-explorer" and method_name == "get_cost_and_usage":
        end = date.today()
        start = end - timedelta(days=7)
        return {
            "TimePeriod": {"Start": str(start), "End": str(end)},
            "Granularity": "DAILY",
            "Metrics": ["UnblendedCost"],
        }

    if service_name == "sagemaker" and method_name == "list_notebook_instances":
        return {}

    return {}


def _determine_region(service_name: str, region: str) -> str:
    """Determine the appropriate region for a given service.

    Some services are global and must use us-east-1:
    - iam: Global service
    - cost-explorer (ce): Global service
    """
    global_services = {"iam", "cost-explorer"}
    if service_name in global_services:
        return "us-east-1"
    return region


def execute_probe(
    service_name: str,
    region: str,
    role_arn: Optional[str] = None,
    external_id: Optional[str] = None,
    profile_name: Optional[str] = None,
    account_id: Optional[str] = None,
    run_id: Optional[str] = None,
) -> ProbeResult:
    """Execute a single service probe and classify the result.

    Calls the lightest possible API for the service and determines whether
    resources are provisioned, not provisioned, or undetermined.

    Args:
        service_name: Key from PROBE_REGISTRY (e.g., 'glue', 's3')
        region: AWS region to probe
        role_arn: Deprecated, ignored.
        external_id: Deprecated, ignored.
        profile_name: Optional AWS profile name from ~/.aws/credentials
        account_id: AWS account ID (for v2.3 role assumption)
        run_id: Assessment run ID (for v2.3 session tagging)

    Returns:
        ProbeResult with classification and resource count
    """
    if service_name not in PROBE_REGISTRY:
        logger.warning("Unknown service '%s' — skipping probe", service_name)
        return ProbeResult(
            service_name=service_name,
            classification=ServiceClassification.UNDETERMINED,
            error_code="UnknownService",
            error_message=f"Service '{service_name}' not in PROBE_REGISTRY",
        )

    api_service, method_name, result_key = PROBE_REGISTRY[service_name]
    effective_region = _determine_region(service_name, region)

    # Create client — use v2.3 role assumption if account_id provided,
    # otherwise fall back to direct session (for standalone probe use)
    if account_id and run_id:
        client = create_client(api_service, effective_region, account_id, run_id, profile_name=profile_name)
    else:
        # Fallback: use boto3 directly with profile (no role assumption)
        import boto3
        sess = boto3.Session(profile_name=profile_name)
        from botocore.config import Config
        client = sess.client(api_service, region_name=effective_region, config=Config(
            retries={"max_attempts": 2, "mode": "adaptive"},
            connect_timeout=5, read_timeout=10,
        ))
    method = getattr(client, method_name)

    # Build any special kwargs for this API call
    call_kwargs = _build_call_kwargs(service_name, method_name)

    # First attempt
    result = safe_call(lambda: method(**call_kwargs))

    if is_error(result):
        error_code = result.get("_code", "")

        # Access denied — mark as undetermined immediately, no retry
        if is_access_denied(result):
            logger.info(
                "Probe %s: access denied (%s)", service_name, error_code
            )
            return ProbeResult(
                service_name=service_name,
                classification=ServiceClassification.UNDETERMINED,
                error_code=error_code,
                error_message=result["_error"],
            )

        # For endpoint/timeout errors, retry once
        logger.info(
            "Probe %s: error '%s', retrying once", service_name, error_code
        )
        result = safe_call(lambda: method(**call_kwargs))

        if is_error(result):
            logger.warning(
                "Probe %s: retry also failed (%s)", service_name, result.get("_code")
            )
            return ProbeResult(
                service_name=service_name,
                classification=ServiceClassification.UNDETERMINED,
                error_code=result.get("_code", ""),
                error_message=result["_error"],
            )

    # Extract resource count for downstream use (e.g., distinguishing
    # "service available but no resources" from "service active with resources")
    count = _extract_resource_count(result, result_key, service_name)

    # A successful API call means the service is accessible in this account.
    # Empty results means "no resources configured" — that's still PROVISIONED.
    # Only actual failures (endpoint errors, service not enabled) indicate
    # NOT_PROVISIONED, and those are handled in the error branches above.
    classification = ServiceClassification.PROVISIONED

    logger.debug(
        "Probe %s: %s (count=%d)", service_name, classification.value, count
    )
    return ProbeResult(
        service_name=service_name,
        classification=classification,
        resource_count=count,
    )


def _extract_resource_count(
    result: dict, result_key: str | None, service_name: str
) -> int:
    """Extract the resource count from an API response.

    Handles special cases like macie2 (status field rather than list)
    and cost-explorer (no result_key, success = provisioned).
    """
    # No result_key means success itself indicates provisioned
    if result_key is None:
        return 1 if result is not None and not is_error(result) else 0

    # Special case: macie2 returns a status string, not a list
    if service_name == "macie2":
        status = result.get(result_key, "")
        # ENABLED or PAUSED means Macie is provisioned
        return 1 if status in ("ENABLED", "PAUSED") else 0

    # Standard case: result_key points to a list of resources
    resources = result.get(result_key, [])
    if isinstance(resources, list):
        return len(resources)
    elif resources:
        return 1
    return 0


def run_probes(
    region: str,
    role_arn: Optional[str] = None,
    external_id: Optional[str] = None,
    profile_name: Optional[str] = None,
    account_id: Optional[str] = None,
    run_id: Optional[str] = None,
) -> list[ProbeResult]:
    """Execute all probes concurrently using a thread pool.

    Uses ThreadPoolExecutor with max_workers=10 and a 60-second timeout
    to ensure the probe phase completes within the target window.

    Args:
        region: AWS region to probe
        role_arn: Deprecated, ignored.
        external_id: Deprecated, ignored.
        profile_name: Optional AWS profile name from ~/.aws/credentials
        account_id: AWS account ID (for v2.3 role assumption)
        run_id: Assessment run ID (for v2.3 session tagging)

    Returns:
        List of ProbeResult for each service in the registry
    """
    results: list[ProbeResult] = []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(execute_probe, svc, region, None, None, profile_name, account_id, run_id): svc
            for svc in PROBE_REGISTRY
        }

        try:
            for future in as_completed(futures, timeout=PROBE_TIMEOUT_SECONDS):
                service_name = futures[future]
                try:
                    probe_result = future.result()
                    results.append(probe_result)
                except Exception as exc:
                    logger.error(
                        "Probe %s raised unexpected exception: %s",
                        service_name, exc,
                    )
                    results.append(ProbeResult(
                        service_name=service_name,
                        classification=ServiceClassification.UNDETERMINED,
                        error_code=type(exc).__name__,
                        error_message=str(exc),
                    ))
        except TimeoutError:
            # Some probes didn't finish within the timeout window
            logger.warning(
                "Probe phase timed out after %ds — marking incomplete probes as UNDETERMINED",
                PROBE_TIMEOUT_SECONDS,
            )
            completed_services = {r.service_name for r in results}
            for svc in PROBE_REGISTRY:
                if svc not in completed_services:
                    results.append(ProbeResult(
                        service_name=svc,
                        classification=ServiceClassification.UNDETERMINED,
                        error_code="TimeoutError",
                        error_message=f"Probe did not complete within {PROBE_TIMEOUT_SECONDS}s",
                    ))

    return results

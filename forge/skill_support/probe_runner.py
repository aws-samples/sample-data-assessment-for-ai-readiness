"""
FORGE 2.1 — Skill Support: Probe Runner

Bridge between the Kiro Skill and the Relevance Engine. Provides high-level
functions for probing an AWS account and validating provisioned services,
returning structured results suitable for display in the skill session.

All functions are importable without CLI context — no argparse, no sys.exit,
no interactive prompts.
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

from forge.models import ProbeResult, ServiceClassification, ValidationResult
from forge.relevance_engine.probes import run_probes
from forge.relevance_engine.validator import validate_service


logger = logging.getLogger(__name__)

# Maximum concurrent validation workers
_VALIDATION_MAX_WORKERS = 5


def probe_account(
    region: str,
    role_arn: Optional[str] = None,
    external_id: Optional[str] = None,
    profile_name: Optional[str] = None,
) -> dict[str, ProbeResult]:
    """Probe an AWS account to discover which services are provisioned.

    Executes all service probes concurrently and returns results keyed
    by service name. This is the primary entry point called by the Kiro
    Skill to detect service availability.

    Args:
        region: AWS region to probe (e.g., "us-east-1").
        role_arn: Optional IAM role ARN for cross-account access.
        external_id: Optional external ID for role assumption.
        profile_name: Optional AWS profile name from ~/.aws/credentials.

    Returns:
        Dict mapping service name to ProbeResult.
    """
    probe_results = run_probes(region, role_arn, external_id, profile_name)
    return {result.service_name: result for result in probe_results}


def validate_provisioned(
    probe_results: dict[str, ProbeResult],
    region: str,
    role_arn: Optional[str] = None,
) -> dict[str, ValidationResult]:
    """Validate all provisioned services against usage signals.

    For each service classified as PROVISIONED in the probe results,
    queries Cost Explorer and CloudTrail to determine confidence scores
    and classify services as active or dormant.

    Uses ThreadPoolExecutor with max_workers=5 for concurrent validation.

    Args:
        probe_results: Dict of service name to ProbeResult (from probe_account).
        region: AWS region for CloudTrail queries.
        role_arn: Optional IAM role ARN for cross-account access.

    Returns:
        Dict mapping service name to ValidationResult for provisioned services.
    """
    # Filter to only provisioned services
    provisioned_services = [
        service_name
        for service_name, result in probe_results.items()
        if result.classification == ServiceClassification.PROVISIONED
    ]

    if not provisioned_services:
        return {}

    validation_results: dict[str, ValidationResult] = {}

    with ThreadPoolExecutor(max_workers=_VALIDATION_MAX_WORKERS) as executor:
        futures = {
            executor.submit(validate_service, svc, region, role_arn): svc
            for svc in provisioned_services
        }

        for future in as_completed(futures):
            service_name = futures[future]
            try:
                result = future.result()
                validation_results[service_name] = result
            except Exception as exc:
                logger.error(
                    "Validation of '%s' raised unexpected exception: %s",
                    service_name, exc,
                )
                # On error, assign a neutral confidence
                validation_results[service_name] = ValidationResult(
                    service_name=service_name,
                    confidence_score=0.5,
                    classification="moderate",
                    cost_access_denied=True,
                    trail_access_denied=True,
                )

    return validation_results

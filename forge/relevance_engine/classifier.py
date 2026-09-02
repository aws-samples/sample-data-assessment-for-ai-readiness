"""
FORGE 2.1 Relevance Engine — Criterion Relevance Classifier

Maps probe and validation results to a RelevanceStatus for each criterion.
Uses OR-semantics: if AT LEAST ONE required service is provisioned and active,
the criterion is relevant. Only when ALL services are not-provisioned (or
all provisioned ones are dormant) does the criterion become not-applicable.

This matches real-world semantics: criteria like "Streaming layer exists
(Kinesis OR MSK)" should be RELEVANT if either service is active.
"""
from forge.models import (
    ProbeResult,
    ValidationResult,
    ServiceClassification,
    RelevanceStatus,
    CriterionDefinition,
)


def classify_criterion_relevance(
    criterion: CriterionDefinition,
    probe_results: dict[str, ProbeResult],
    validation_results: dict[str, ValidationResult],
) -> tuple[RelevanceStatus, str]:
    """
    Determine relevance status for a criterion based on its required services.

    Logic (OR-semantics — at least one active service = relevant):
    - Criteria with no service dependencies are always RELEVANT.
    - If at least one service is PROVISIONED and active → RELEVANT.
    - If ALL services are NOT_PROVISIONED → NOT_APPLICABLE.
    - If all provisioned services are dormant → NOT_APPLICABLE.
    - If we only have undetermined results → UNDETERMINED.
    - Otherwise → RELEVANT (fallback).

    Args:
        criterion: The criterion definition including its service dependencies.
        probe_results: Dict mapping service name to its ProbeResult.
        validation_results: Dict mapping service name to its ValidationResult.

    Returns:
        A tuple of (RelevanceStatus, reason) where reason is a human-readable
        justification for the classification.
    """
    if not criterion.services:
        return RelevanceStatus.RELEVANT, "No service dependency"

    # Track status of each service
    has_provisioned = False
    has_undetermined = False
    all_not_provisioned = True
    all_dormant = True
    any_probe_found = False

    for service in criterion.services:
        probe = probe_results.get(service)

        if not probe:
            # No probe result available for this service — skip it
            continue

        any_probe_found = True

        if probe.classification == ServiceClassification.PROVISIONED:
            all_not_provisioned = False
            # Check if dormant
            validation = validation_results.get(service)
            if not validation or validation.classification != "dormant":
                all_dormant = False
                has_provisioned = True
            # else: provisioned but dormant — don't set has_provisioned
        elif probe.classification == ServiceClassification.UNDETERMINED:
            all_not_provisioned = False
            all_dormant = False
            has_undetermined = True
        # NOT_PROVISIONED: remains in all_not_provisioned

    # If at least one service is provisioned and active → RELEVANT
    if has_provisioned:
        return RelevanceStatus.RELEVANT, "At least one required service is active"

    # If no probes were found for any listed service, treat as RELEVANT
    # (we simply don't have data to exclude the criterion)
    if not any_probe_found:
        return RelevanceStatus.RELEVANT, "No probe data available for listed services"

    # If all services are not provisioned → NOT_APPLICABLE
    if all_not_provisioned:
        services_str = ", ".join(criterion.services)
        return (
            RelevanceStatus.NOT_APPLICABLE,
            f"None of the required services ({services_str}) are provisioned",
        )

    # If all provisioned services are dormant → NOT_APPLICABLE
    if all_dormant and not has_undetermined:
        return (
            RelevanceStatus.NOT_APPLICABLE,
            "All provisioned services are dormant",
        )

    # If we only have undetermined → UNDETERMINED
    if has_undetermined:
        return (
            RelevanceStatus.UNDETERMINED,
            "Could not determine status of required services",
        )

    return RelevanceStatus.RELEVANT, "Service available"

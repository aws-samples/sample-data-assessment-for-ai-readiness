"""
Unit tests for forge.relevance_engine.classifier module.

Tests criterion relevance classification based on probe and validation results.
Uses OR-semantics: at least one active service = RELEVANT.
"""
import pytest
from forge.relevance_engine.classifier import classify_criterion_relevance
from forge.models import (
    ProbeResult,
    ValidationResult,
    ServiceClassification,
    RelevanceStatus,
    CriterionDefinition,
    CriterionType,
)


def _criterion(services: list[str]) -> CriterionDefinition:
    """Helper to create a criterion with given service dependencies."""
    return CriterionDefinition(
        pillar="P1",
        index=1,
        name="Test Criterion",
        criterion_type=CriterionType.BINARY,
        services=services,
    )


def _probe(service: str, classification: ServiceClassification, **kwargs) -> ProbeResult:
    """Helper to create a ProbeResult."""
    return ProbeResult(service_name=service, classification=classification, **kwargs)


def _validation(service: str, classification: str, confidence: float) -> ValidationResult:
    """Helper to create a ValidationResult."""
    return ValidationResult(
        service_name=service,
        confidence_score=confidence,
        classification=classification,
    )


class TestEmptyServices:
    """Criteria with no service dependencies."""

    def test_empty_services_list_is_relevant(self):
        """Criteria with no services are always RELEVANT."""
        criterion = _criterion(services=[])
        status, reason = classify_criterion_relevance(criterion, {}, {})
        assert status == RelevanceStatus.RELEVANT
        assert reason == "No service dependency"

    def test_empty_services_ignores_probe_results(self):
        """Even with probe data available, empty services → RELEVANT."""
        criterion = _criterion(services=[])
        probes = {"s3": _probe("s3", ServiceClassification.NOT_PROVISIONED)}
        status, _ = classify_criterion_relevance(criterion, probes, {})
        assert status == RelevanceStatus.RELEVANT


class TestNotProvisioned:
    """All services NOT_PROVISIONED → criterion NOT_APPLICABLE."""

    def test_single_service_not_provisioned(self):
        """A single service that's not provisioned → NOT_APPLICABLE."""
        criterion = _criterion(services=["kinesis"])
        probes = {"kinesis": _probe("kinesis", ServiceClassification.NOT_PROVISIONED)}
        status, reason = classify_criterion_relevance(criterion, probes, {})
        assert status == RelevanceStatus.NOT_APPLICABLE
        assert "kinesis" in reason

    def test_all_services_not_provisioned(self):
        """All services not provisioned → NOT_APPLICABLE."""
        criterion = _criterion(services=["kinesis", "msk"])
        probes = {
            "kinesis": _probe("kinesis", ServiceClassification.NOT_PROVISIONED),
            "msk": _probe("msk", ServiceClassification.NOT_PROVISIONED),
        }
        status, reason = classify_criterion_relevance(criterion, probes, {})
        assert status == RelevanceStatus.NOT_APPLICABLE
        assert "kinesis" in reason or "msk" in reason

    def test_one_not_provisioned_one_active_is_relevant(self):
        """OR-semantics: if one service is active, criterion is RELEVANT."""
        criterion = _criterion(services=["kinesis", "s3"])
        probes = {
            "kinesis": _probe("kinesis", ServiceClassification.NOT_PROVISIONED),
            "s3": _probe("s3", ServiceClassification.PROVISIONED),
        }
        validations = {"s3": _validation("s3", "active", 0.9)}
        status, reason = classify_criterion_relevance(criterion, probes, validations)
        assert status == RelevanceStatus.RELEVANT

    def test_one_active_one_not_provisioned_is_relevant(self):
        """OR-semantics: order doesn't matter — active service wins."""
        criterion = _criterion(services=["s3", "kinesis"])
        probes = {
            "s3": _probe("s3", ServiceClassification.PROVISIONED),
            "kinesis": _probe("kinesis", ServiceClassification.NOT_PROVISIONED),
        }
        validations = {"s3": _validation("s3", "active", 0.9)}
        status, reason = classify_criterion_relevance(criterion, probes, validations)
        assert status == RelevanceStatus.RELEVANT


class TestUndetermined:
    """Service UNDETERMINED handling."""

    def test_single_service_undetermined(self):
        """Single undetermined service → UNDETERMINED."""
        criterion = _criterion(services=["glue"])
        probes = {
            "glue": _probe(
                "glue",
                ServiceClassification.UNDETERMINED,
                error_code="AccessDeniedException",
                error_message="Access denied to glue:GetDatabases",
            ),
        }
        status, reason = classify_criterion_relevance(criterion, probes, {})
        assert status == RelevanceStatus.UNDETERMINED

    def test_undetermined_with_active_service_is_relevant(self):
        """OR-semantics: one active + one undetermined → RELEVANT."""
        criterion = _criterion(services=["kinesis", "glue"])
        probes = {
            "kinesis": _probe("kinesis", ServiceClassification.PROVISIONED),
            "glue": _probe("glue", ServiceClassification.UNDETERMINED),
        }
        validations = {"kinesis": _validation("kinesis", "active", 0.8)}
        status, _ = classify_criterion_relevance(criterion, probes, validations)
        assert status == RelevanceStatus.RELEVANT

    def test_all_undetermined(self):
        """All services undetermined → UNDETERMINED."""
        criterion = _criterion(services=["kinesis", "glue"])
        probes = {
            "kinesis": _probe("kinesis", ServiceClassification.UNDETERMINED),
            "glue": _probe("glue", ServiceClassification.UNDETERMINED),
        }
        status, _ = classify_criterion_relevance(criterion, probes, {})
        assert status == RelevanceStatus.UNDETERMINED

    def test_not_provisioned_and_undetermined_no_active(self):
        """Mix of not-provisioned and undetermined, no active → UNDETERMINED."""
        criterion = _criterion(services=["kinesis", "glue", "msk"])
        probes = {
            "kinesis": _probe("kinesis", ServiceClassification.NOT_PROVISIONED),
            "glue": _probe("glue", ServiceClassification.UNDETERMINED),
            "msk": _probe("msk", ServiceClassification.NOT_PROVISIONED),
        }
        status, _ = classify_criterion_relevance(criterion, probes, {})
        assert status == RelevanceStatus.UNDETERMINED


class TestDormant:
    """Provisioned but dormant service handling."""

    def test_single_dormant_service(self):
        """Single service that's provisioned but dormant → NOT_APPLICABLE."""
        criterion = _criterion(services=["neptune"])
        probes = {"neptune": _probe("neptune", ServiceClassification.PROVISIONED)}
        validations = {"neptune": _validation("neptune", "dormant", 0.05)}
        status, reason = classify_criterion_relevance(criterion, probes, validations)
        assert status == RelevanceStatus.NOT_APPLICABLE
        assert "dormant" in reason

    def test_all_dormant(self):
        """All provisioned services are dormant → NOT_APPLICABLE."""
        criterion = _criterion(services=["neptune", "opensearch"])
        probes = {
            "neptune": _probe("neptune", ServiceClassification.PROVISIONED),
            "opensearch": _probe("opensearch", ServiceClassification.PROVISIONED),
        }
        validations = {
            "neptune": _validation("neptune", "dormant", 0.05),
            "opensearch": _validation("opensearch", "dormant", 0.1),
        }
        status, reason = classify_criterion_relevance(criterion, probes, validations)
        assert status == RelevanceStatus.NOT_APPLICABLE
        assert "dormant" in reason

    def test_one_dormant_one_active_is_relevant(self):
        """OR-semantics: one dormant + one active → RELEVANT."""
        criterion = _criterion(services=["neptune", "glue"])
        probes = {
            "neptune": _probe("neptune", ServiceClassification.PROVISIONED),
            "glue": _probe("glue", ServiceClassification.PROVISIONED),
        }
        validations = {
            "neptune": _validation("neptune", "dormant", 0.1),
            "glue": _validation("glue", "active", 0.9),
        }
        status, _ = classify_criterion_relevance(criterion, probes, validations)
        assert status == RelevanceStatus.RELEVANT

    def test_dormant_and_undetermined(self):
        """Dormant + undetermined (no active) → UNDETERMINED (not enough info)."""
        criterion = _criterion(services=["neptune", "glue"])
        probes = {
            "neptune": _probe("neptune", ServiceClassification.PROVISIONED),
            "glue": _probe("glue", ServiceClassification.UNDETERMINED),
        }
        validations = {"neptune": _validation("neptune", "dormant", 0.1)}
        status, _ = classify_criterion_relevance(criterion, probes, validations)
        assert status == RelevanceStatus.UNDETERMINED


class TestRelevant:
    """At least one active service → criterion RELEVANT."""

    def test_single_active_service(self):
        criterion = _criterion(services=["s3"])
        probes = {"s3": _probe("s3", ServiceClassification.PROVISIONED)}
        validations = {"s3": _validation("s3", "active", 0.9)}
        status, reason = classify_criterion_relevance(criterion, probes, validations)
        assert status == RelevanceStatus.RELEVANT

    def test_multiple_active_services(self):
        criterion = _criterion(services=["s3", "glue", "athena"])
        probes = {
            "s3": _probe("s3", ServiceClassification.PROVISIONED),
            "glue": _probe("glue", ServiceClassification.PROVISIONED),
            "athena": _probe("athena", ServiceClassification.PROVISIONED),
        }
        validations = {
            "s3": _validation("s3", "active", 0.95),
            "glue": _validation("glue", "active", 0.8),
            "athena": _validation("athena", "active", 0.75),
        }
        status, reason = classify_criterion_relevance(criterion, probes, validations)
        assert status == RelevanceStatus.RELEVANT

    def test_moderate_classification_treated_as_relevant(self):
        """A 'moderate' validation classification results in RELEVANT."""
        criterion = _criterion(services=["dynamodb"])
        probes = {"dynamodb": _probe("dynamodb", ServiceClassification.PROVISIONED)}
        validations = {"dynamodb": _validation("dynamodb", "moderate", 0.5)}
        status, _ = classify_criterion_relevance(criterion, probes, validations)
        assert status == RelevanceStatus.RELEVANT

    def test_provisioned_without_validation_result(self):
        """Provisioned service with no validation entry is treated as relevant."""
        criterion = _criterion(services=["lambda"])
        probes = {"lambda": _probe("lambda", ServiceClassification.PROVISIONED)}
        status, _ = classify_criterion_relevance(criterion, probes, {})
        assert status == RelevanceStatus.RELEVANT


class TestMissingProbeResults:
    """Services not in probe_results dict are skipped."""

    def test_service_not_in_probes_skipped(self):
        """If a service has no probe result, it's skipped."""
        criterion = _criterion(services=["unknown_service"])
        status, reason = classify_criterion_relevance(criterion, {}, {})
        assert status == RelevanceStatus.RELEVANT

    def test_partial_probes_mixed(self):
        """Only services with probe results are evaluated."""
        criterion = _criterion(services=["s3", "missing_service"])
        probes = {"s3": _probe("s3", ServiceClassification.PROVISIONED)}
        validations = {"s3": _validation("s3", "active", 0.9)}
        status, _ = classify_criterion_relevance(criterion, probes, validations)
        assert status == RelevanceStatus.RELEVANT


class TestORSemantics:
    """Verify OR-semantics for multi-service criteria (the streaming layer case)."""

    def test_streaming_kinesis_active_msk_not_provisioned(self):
        """Kinesis active + MSK not provisioned → criterion RELEVANT."""
        criterion = _criterion(services=["kinesis", "msk"])
        probes = {
            "kinesis": _probe("kinesis", ServiceClassification.PROVISIONED, resource_count=3),
            "msk": _probe("msk", ServiceClassification.NOT_PROVISIONED),
        }
        validations = {"kinesis": _validation("kinesis", "active", 0.85)}
        status, _ = classify_criterion_relevance(criterion, probes, validations)
        assert status == RelevanceStatus.RELEVANT

    def test_msk_active_kinesis_not_provisioned(self):
        """MSK active + Kinesis not provisioned → criterion RELEVANT."""
        criterion = _criterion(services=["kinesis", "msk"])
        probes = {
            "kinesis": _probe("kinesis", ServiceClassification.NOT_PROVISIONED),
            "msk": _probe("msk", ServiceClassification.PROVISIONED, resource_count=1),
        }
        validations = {"msk": _validation("msk", "active", 0.9)}
        status, _ = classify_criterion_relevance(criterion, probes, validations)
        assert status == RelevanceStatus.RELEVANT

    def test_both_not_provisioned(self):
        """Both Kinesis and MSK not provisioned → NOT_APPLICABLE."""
        criterion = _criterion(services=["kinesis", "msk"])
        probes = {
            "kinesis": _probe("kinesis", ServiceClassification.NOT_PROVISIONED),
            "msk": _probe("msk", ServiceClassification.NOT_PROVISIONED),
        }
        status, _ = classify_criterion_relevance(criterion, probes, {})
        assert status == RelevanceStatus.NOT_APPLICABLE

    def test_bedrock_and_bedrock_agent_one_active(self):
        """bedrock-agent active + bedrock not provisioned → RELEVANT."""
        criterion = _criterion(services=["bedrock", "bedrock-agent"])
        probes = {
            "bedrock": _probe("bedrock", ServiceClassification.NOT_PROVISIONED),
            "bedrock-agent": _probe("bedrock-agent", ServiceClassification.PROVISIONED, resource_count=2),
        }
        validations = {"bedrock-agent": _validation("bedrock-agent", "active", 0.9)}
        status, _ = classify_criterion_relevance(criterion, probes, validations)
        assert status == RelevanceStatus.RELEVANT


class TestNoCLICoupling:
    """Verify the module has no CLI dependencies."""

    def test_no_argparse_or_sys_exit(self):
        import forge.relevance_engine.classifier as mod
        import inspect

        source = inspect.getsource(mod)
        assert "argparse" not in source
        assert "sys.exit" not in source

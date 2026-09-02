"""
Unit tests for forge.relevance_engine.validator module.

Tests confidence scoring, service classification, and validate_service structure.
"""
import pytest
from unittest.mock import patch, MagicMock
from forge.relevance_engine.validator import (
    compute_confidence,
    classify_service,
    validate_service,
)
from forge.models import ValidationResult


class TestComputeConfidence:
    """Tests for compute_confidence() function."""

    def test_both_signals_none_returns_0_5(self):
        """When both signals are unavailable, return neutral 0.5."""
        assert compute_confidence(None, None) == 0.5

    def test_zero_cost_zero_events_returns_zero(self):
        """cost=0, events=0 → confidence = 0.0 (dormant)."""
        assert compute_confidence(0.0, 0) == 0.0

    def test_zero_cost_few_events_below_0_2(self):
        """cost=0, events<10 → confidence < 0.2."""
        for events in range(0, 10):
            c = compute_confidence(0.0, events)
            assert c < 0.2, f"events={events} gave confidence={c}"

    def test_positive_cost_above_0_7(self):
        """cost>0 → confidence > 0.7."""
        assert compute_confidence(10.0, 0) > 0.7
        assert compute_confidence(0.01, 5) > 0.7

    def test_events_above_50_above_0_7(self):
        """events>50 → confidence > 0.7."""
        assert compute_confidence(0.0, 51) > 0.7
        assert compute_confidence(0.0, 200) > 0.7

    def test_moderate_range_10_to_50_events(self):
        """10 <= events <= 50, cost=0 → confidence in [0.2, 0.7]."""
        for events in [10, 20, 30, 40, 50]:
            c = compute_confidence(0.0, events)
            assert 0.2 <= c <= 0.7, f"events={events} gave confidence={c}"

    def test_cost_none_trail_few_events_dormant(self):
        """Cost unavailable, few trail events → dormant."""
        c = compute_confidence(None, 3)
        assert c < 0.2

    def test_cost_none_trail_active(self):
        """Cost unavailable, many trail events → active."""
        c = compute_confidence(None, 100)
        assert c > 0.7

    def test_confidence_always_in_range(self):
        """All outputs must be in [0.0, 1.0]."""
        test_cases = [
            (None, None), (0.0, 0), (0.0, 9), (0.0, 10),
            (0.0, 50), (0.0, 51), (100.0, 200),
            (None, 0), (None, 100), (50.0, None),
        ]
        for cost, events in test_cases:
            c = compute_confidence(cost, events)
            assert 0.0 <= c <= 1.0, f"cost={cost}, events={events} → {c}"


class TestClassifyService:
    """Tests for classify_service() function."""

    def test_dormant_below_0_2(self):
        assert classify_service(0.0) == "dormant"
        assert classify_service(0.1) == "dormant"
        assert classify_service(0.19) == "dormant"

    def test_active_above_0_7(self):
        assert classify_service(0.71) == "active"
        assert classify_service(0.9) == "active"
        assert classify_service(1.0) == "active"

    def test_moderate_between_0_2_and_0_7(self):
        assert classify_service(0.2) == "moderate"
        assert classify_service(0.5) == "moderate"
        assert classify_service(0.7) == "moderate"

    def test_boundary_0_2_is_moderate(self):
        """Exactly 0.2 is moderate (not dormant)."""
        assert classify_service(0.2) == "moderate"

    def test_boundary_0_7_is_moderate(self):
        """Exactly 0.7 is moderate (not active)."""
        assert classify_service(0.7) == "moderate"


class TestValidateService:
    """Tests for validate_service() function structure and fallback behavior."""

    @patch("forge.relevance_engine.validator.create_client")
    def test_returns_validation_result(self, mock_create):
        """validate_service returns a ValidationResult dataclass."""
        # Mock both clients to return access denied
        mock_client = MagicMock()
        mock_client.get_cost_and_usage.side_effect = Exception("NoCredentials")
        mock_client.lookup_events.side_effect = Exception("NoCredentials")
        mock_create.return_value = mock_client

        result = validate_service("glue", "us-east-1")
        assert isinstance(result, ValidationResult)
        assert result.service_name == "glue"
        assert 0.0 <= result.confidence_score <= 1.0
        assert result.classification in ("dormant", "active", "moderate")

    @patch("forge.relevance_engine.validator.create_client")
    def test_both_denied_returns_0_5(self, mock_create):
        """When both CE and CT are access denied, confidence = 0.5."""
        from botocore.exceptions import ClientError

        error_response = {"Error": {"Code": "AccessDeniedException", "Message": "denied"}}
        mock_client = MagicMock()
        mock_client.get_cost_and_usage.side_effect = ClientError(error_response, "GetCostAndUsage")
        mock_client.lookup_events.side_effect = ClientError(error_response, "LookupEvents")
        mock_create.return_value = mock_client

        result = validate_service("s3", "us-east-1")
        assert result.confidence_score == 0.5
        assert result.cost_access_denied is True
        assert result.trail_access_denied is True

    @patch("forge.relevance_engine.validator.create_client")
    def test_cost_denied_relies_on_trail(self, mock_create):
        """When Cost Explorer is denied, rely on CloudTrail only."""
        from botocore.exceptions import ClientError

        error_response = {"Error": {"Code": "AccessDeniedException", "Message": "denied"}}

        mock_ce = MagicMock()
        mock_ce.get_cost_and_usage.side_effect = ClientError(error_response, "GetCostAndUsage")

        mock_ct = MagicMock()
        mock_ct.lookup_events.return_value = {"Events": [{"EventId": str(i)} for i in range(100)]}

        # Return different mocks based on service name
        def create_side_effect(service, region, role_arn=None):
            if service == "ce":
                return mock_ce
            return mock_ct

        mock_create.side_effect = create_side_effect

        result = validate_service("glue", "us-east-1")
        assert result.cost_access_denied is True
        assert result.trail_access_denied is False
        # With 50 events (MaxResults=50 in query, mock returns 100 but lookup_events is called directly)
        # The trail shows activity so confidence should be > 0.7
        assert result.confidence_score > 0.7
        assert result.classification == "active"

    @patch("forge.relevance_engine.validator.create_client")
    def test_active_service_with_cost(self, mock_create):
        """Service with positive cost classified as active."""
        mock_ce = MagicMock()
        mock_ce.get_cost_and_usage.return_value = {
            "ResultsByTime": [
                {"Total": {"UnblendedCost": {"Amount": "15.50"}}},
                {"Total": {"UnblendedCost": {"Amount": "12.30"}}},
                {"Total": {"UnblendedCost": {"Amount": "18.20"}}},
            ]
        }

        mock_ct = MagicMock()
        mock_ct.lookup_events.return_value = {"Events": [{"EventId": str(i)} for i in range(30)]}

        def create_side_effect(service, region, role_arn=None):
            if service == "ce":
                return mock_ce
            return mock_ct

        mock_create.side_effect = create_side_effect

        result = validate_service("glue", "us-east-1")
        assert result.cost_90d == pytest.approx(46.0)
        assert result.trail_event_count == 30
        assert result.confidence_score > 0.7
        assert result.classification == "active"

    @patch("forge.relevance_engine.validator.create_client")
    def test_dormant_service(self, mock_create):
        """Service with zero cost and few events classified as dormant."""
        mock_ce = MagicMock()
        mock_ce.get_cost_and_usage.return_value = {
            "ResultsByTime": [
                {"Total": {"UnblendedCost": {"Amount": "0.00"}}},
                {"Total": {"UnblendedCost": {"Amount": "0.00"}}},
                {"Total": {"UnblendedCost": {"Amount": "0.00"}}},
            ]
        }

        mock_ct = MagicMock()
        mock_ct.lookup_events.return_value = {"Events": [{"EventId": "1"}, {"EventId": "2"}]}

        def create_side_effect(service, region, role_arn=None):
            if service == "ce":
                return mock_ce
            return mock_ct

        mock_create.side_effect = create_side_effect

        result = validate_service("neptune", "us-east-1")
        assert result.cost_90d == 0.0
        assert result.trail_event_count == 2
        assert result.confidence_score < 0.2
        assert result.classification == "dormant"

    def test_no_cli_coupling(self):
        """Module has no argparse or sys.exit dependencies."""
        import forge.relevance_engine.validator as mod
        import inspect

        source = inspect.getsource(mod)
        assert "argparse" not in source
        assert "sys.exit" not in source

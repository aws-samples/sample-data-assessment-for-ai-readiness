"""
FORGE 2.1 — Relevance Engine: Service Validator

Validates provisioned services against usage signals from AWS Cost Explorer
and CloudTrail to assign confidence scores and classify activity level.

Confidence scoring rules:
- cost=0 AND events<10 → confidence < 0.2 → "dormant"
- cost>0 OR events>50 → confidence > 0.7 → "active"
- Otherwise → linear interpolation → "moderate" (treated as active for scoring)
- If Cost Explorer denied → rely on CloudTrail only
- If both denied → confidence = 0.5
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

from forge.models import ValidationResult
from forge.aws_client import create_client, safe_call, is_error, is_access_denied


def compute_confidence(
    cost_90d: Optional[float],
    trail_event_count: Optional[int],
) -> float:
    """Compute confidence score from cost and trail signals.

    Maps cost and CloudTrail activity signals to a confidence value
    in [0.0, 1.0] indicating how actively a service is being used.

    Args:
        cost_90d: Total cost over the last 90 days, or None if unavailable.
        trail_event_count: Number of CloudTrail events in 30 days, or None if unavailable.

    Returns:
        Confidence score between 0.0 and 1.0.

    Rules:
        - Both signals unavailable → 0.5 (neutral default)
        - cost=0 AND events<10 → score < 0.2 (dormant)
        - cost>0 OR events>50 → score > 0.7 (active)
        - Otherwise → linear interpolation in [0.2, 0.7]
    """
    # Both signals unavailable → default 0.5
    if cost_90d is None and trail_event_count is None:
        return 0.5

    cost = cost_90d if cost_90d is not None else 0.0
    events = trail_event_count if trail_event_count is not None else 0

    # Active threshold: cost > 0 OR events > 50
    if cost > 0 or events > 50:
        # Scale between 0.7 and 1.0 based on signal strength
        cost_signal = min(cost / 100.0, 1.0) if cost > 0 else 0.0
        event_signal = min(events / 200.0, 1.0)
        return 0.7 + 0.3 * max(cost_signal, event_signal)

    # Dormant threshold: cost == 0 AND events < 10
    if cost == 0 and events < 10:
        # Linear scale from 0.0 to 0.18 based on event count
        return 0.02 * events

    # Middle ground: 10–50 events with no cost
    # Linear interpolation from 0.2 to 0.7
    return 0.2 + (events - 10) * (0.5 / 40)


def classify_service(confidence: float) -> str:
    """Classify service activity level based on confidence score.

    Args:
        confidence: Confidence score in [0.0, 1.0].

    Returns:
        Classification string: "dormant" (<0.2), "active" (>0.7),
        or "moderate" (0.2–0.7, treated as active for scoring).
    """
    if confidence < 0.2:
        return "dormant"
    elif confidence > 0.7:
        return "active"
    else:
        return "moderate"


def validate_service(
    service_name: str, region: str, role_arn: Optional[str] = None,
    profile_name: Optional[str] = None,
) -> ValidationResult:
    """Validate a provisioned service using Cost Explorer and CloudTrail.

    Queries AWS Cost Explorer for 90-day cost data and CloudTrail for
    30-day API activity. Handles AccessDenied gracefully by falling back
    to available signals.

    Args:
        service_name: AWS service name to validate (e.g., "glue", "s3").
        region: AWS region for CloudTrail queries.
        role_arn: Deprecated, ignored.
        profile_name: Optional AWS profile name.

    Returns:
        ValidationResult with confidence score, classification, and signal details.
    """
    cost_90d = None
    trail_count = None
    cost_denied = False
    trail_denied = False

    # Query Cost Explorer (always us-east-1 endpoint)
    cost_90d, cost_denied = _query_cost_explorer(service_name, profile_name)

    # Query CloudTrail
    trail_count, trail_denied = _query_cloudtrail(service_name, region, profile_name)

    # Compute confidence from available signals
    confidence = compute_confidence(
        cost_90d if not cost_denied else None,
        trail_count if not trail_denied else None,
    )
    classification = classify_service(confidence)

    return ValidationResult(
        service_name=service_name,
        confidence_score=confidence,
        classification=classification,
        cost_90d=cost_90d,
        trail_event_count=trail_count,
        cost_access_denied=cost_denied,
        trail_access_denied=trail_denied,
    )


def _query_cost_explorer(
    service_name: str, profile_name: Optional[str] = None
) -> tuple[Optional[float], bool]:
    """Query Cost Explorer for 90-day cost data.

    Returns:
        Tuple of (cost_amount_or_None, access_denied_flag).
    """
    import boto3
    from botocore.config import Config
    sess = boto3.Session(profile_name=profile_name)
    ce = sess.client("ce", region_name="us-east-1", config=Config(
        retries={"max_attempts": 2, "mode": "adaptive"}, connect_timeout=5, read_timeout=10,
    ))
    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=90)

    result = safe_call(
        lambda: ce.get_cost_and_usage(
            TimePeriod={"Start": str(start), "End": str(end)},
            Granularity="MONTHLY",
            Metrics=["UnblendedCost"],
            Filter={"Dimensions": {"Key": "SERVICE", "Values": [service_name]}},
        )
    )

    if is_error(result):
        if is_access_denied(result):
            return None, True
        # Non-access-denied error: treat cost as unavailable
        return None, False

    # Sum up costs across all time periods
    total_cost = sum(
        float(period["Total"]["UnblendedCost"]["Amount"])
        for period in result.get("ResultsByTime", [])
    )
    return total_cost, False


def _query_cloudtrail(
    service_name: str, region: str, profile_name: Optional[str] = None
) -> tuple[Optional[int], bool]:
    """Query CloudTrail for 30-day API activity.

    Returns:
        Tuple of (event_count_or_None, access_denied_flag).
    """
    import boto3
    from botocore.config import Config
    sess = boto3.Session(profile_name=profile_name)
    ct = sess.client("cloudtrail", region_name=region, config=Config(
        retries={"max_attempts": 2, "mode": "adaptive"}, connect_timeout=5, read_timeout=10,
    ))
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(days=30)

    result = safe_call(
        lambda: ct.lookup_events(
            LookupAttributes=[
                {
                    "AttributeKey": "EventSource",
                    "AttributeValue": f"{service_name}.amazonaws.com",
                }
            ],
            StartTime=start_time,
            EndTime=end_time,
            MaxResults=50,
        )
    )

    if is_error(result):
        if is_access_denied(result):
            return None, True
        # Non-access-denied error: treat trail as unavailable
        return None, False

    event_count = len(result.get("Events", []))
    return event_count, False

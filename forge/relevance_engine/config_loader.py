"""
FORGE 2.3 — Relevance Configuration Loader

Loads the pre-computed relevance configuration JSON produced by the Kiro Skill
(via config_generator.py) and maps it into internal model types for the
scoring pipeline.

The expected JSON schema:
{
    "generated_at": "<ISO 8601 timestamp>",
    "services": {
        "<service_name>": {
            "status": "provisioned" | "not_provisioned" | "undetermined",
            "confidence": <float 0.0-1.0>,
            "classification": "active" | "dormant" | "moderate"
        },
        ...
    },
    "criteria_relevance": {
        "<criterion_id>": "relevant" | "not-applicable" | "undetermined",
        ...
    }
}
"""
import json
from pathlib import Path
from typing import Union

from forge.models import RelevanceConfig, RelevanceStatus


_REQUIRED_FIELDS = ("services", "criteria_relevance", "generated_at")

_VALID_RELEVANCE_STATUSES = {s.value for s in RelevanceStatus}


def load_relevance_config(path: Union[str, Path]) -> RelevanceConfig:
    """Load and validate a relevance configuration JSON file.

    Args:
        path: File path to the relevance-config JSON produced by
              the Kiro Skill's config_generator.

    Returns:
        A populated RelevanceConfig dataclass ready for the scoring pipeline.

    Raises:
        ValueError: If the file cannot be read, parsed, or fails schema
                    validation (missing fields, invalid values).
        FileNotFoundError: If the file does not exist at the given path.
    """
    config_path = Path(path)

    if not config_path.exists():
        raise FileNotFoundError(
            f"Relevance config file not found: {config_path}"
        )

    try:
        raw_text = config_path.read_text(encoding="utf-8")
    except OSError as e:
        raise ValueError(
            f"Unable to read relevance config file '{config_path}': {e}"
        ) from e

    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Invalid JSON in relevance config file '{config_path}': {e}"
        ) from e

    _validate_schema(data, config_path)

    return _map_to_model(data)


def _validate_schema(data: dict, source_path: Path) -> None:
    """Validate that the parsed JSON conforms to the expected schema.

    Raises ValueError with descriptive messages on any validation failure.
    """
    if not isinstance(data, dict):
        raise ValueError(
            f"Relevance config must be a JSON object, got {type(data).__name__}"
        )

    # Check required top-level fields
    missing = [f for f in _REQUIRED_FIELDS if f not in data]
    if missing:
        raise ValueError(
            f"Relevance config is missing required fields: {', '.join(missing)}"
        )

    # Validate generated_at is a non-empty string
    generated_at = data["generated_at"]
    if not isinstance(generated_at, str) or not generated_at.strip():
        raise ValueError(
            "Field 'generated_at' must be a non-empty ISO 8601 timestamp string"
        )

    # Validate services structure
    services = data["services"]
    if not isinstance(services, dict):
        raise ValueError(
            f"Field 'services' must be an object, got {type(services).__name__}"
        )
    for svc_name, svc_data in services.items():
        if not isinstance(svc_data, dict):
            raise ValueError(
                f"Service entry '{svc_name}' must be an object, "
                f"got {type(svc_data).__name__}"
            )
        if "status" not in svc_data:
            raise ValueError(
                f"Service entry '{svc_name}' is missing required field 'status'"
            )
        if "confidence" not in svc_data:
            raise ValueError(
                f"Service entry '{svc_name}' is missing required field 'confidence'"
            )
        confidence = svc_data["confidence"]
        if not isinstance(confidence, (int, float)):
            raise ValueError(
                f"Service '{svc_name}' confidence must be a number, "
                f"got {type(confidence).__name__}"
            )
        if not (0.0 <= confidence <= 1.0):
            raise ValueError(
                f"Service '{svc_name}' confidence must be between 0.0 and 1.0, "
                f"got {confidence}"
            )

    # Validate criteria_relevance structure
    criteria = data["criteria_relevance"]
    if not isinstance(criteria, dict):
        raise ValueError(
            f"Field 'criteria_relevance' must be an object, "
            f"got {type(criteria).__name__}"
        )
    for crit_id, status_value in criteria.items():
        if status_value not in _VALID_RELEVANCE_STATUSES:
            raise ValueError(
                f"Criterion '{crit_id}' has invalid relevance status "
                f"'{status_value}'. Must be one of: "
                f"{', '.join(sorted(_VALID_RELEVANCE_STATUSES))}"
            )


def _map_to_model(data: dict) -> RelevanceConfig:
    """Map validated JSON data into a RelevanceConfig dataclass with typed values."""
    # Services dict preserves structure as-is for downstream consumption
    services = data["services"]

    # Map criteria_relevance string values to RelevanceStatus enums
    criteria_relevance = {
        crit_id: RelevanceStatus(status_str)
        for crit_id, status_str in data["criteria_relevance"].items()
    }

    return RelevanceConfig(
        services=services,
        criteria_relevance=criteria_relevance,
        generated_at=data["generated_at"],
    )

"""
Unit tests for forge.relevance_config_loader module.

Tests JSON loading, schema validation, and mapping to internal model types.
"""
import json
import pytest
from pathlib import Path

from forge.relevance_config_loader import load_relevance_config
from forge.models import RelevanceConfig, RelevanceStatus


@pytest.fixture
def valid_config_data():
    """Return a valid relevance config dictionary."""
    return {
        "generated_at": "2025-01-15T10:30:00Z",
        "services": {
            "glue": {"status": "provisioned", "confidence": 0.95, "classification": "active"},
            "kinesis": {"status": "not_provisioned", "confidence": 0.0, "classification": "dormant"},
        },
        "criteria_relevance": {
            "P1.1": "relevant",
            "P1.16": "not-applicable",
            "P2.3": "undetermined",
        },
    }


@pytest.fixture
def config_file(tmp_path, valid_config_data):
    """Write a valid config JSON and return its path."""
    path = tmp_path / "relevance-config.json"
    path.write_text(json.dumps(valid_config_data), encoding="utf-8")
    return path


class TestLoadRelevanceConfigHappyPath:
    """Tests for successful loading and mapping."""

    def test_loads_valid_config(self, config_file):
        """Valid JSON file produces a RelevanceConfig dataclass."""
        result = load_relevance_config(config_file)
        assert isinstance(result, RelevanceConfig)

    def test_preserves_services_dict(self, config_file):
        """Services dict is passed through with full structure."""
        result = load_relevance_config(config_file)
        assert "glue" in result.services
        assert result.services["glue"]["confidence"] == 0.95
        assert result.services["glue"]["status"] == "provisioned"

    def test_maps_criteria_relevance_to_enums(self, config_file):
        """Criteria relevance values are mapped to RelevanceStatus enums."""
        result = load_relevance_config(config_file)
        assert result.criteria_relevance["P1.1"] == RelevanceStatus.RELEVANT
        assert result.criteria_relevance["P1.16"] == RelevanceStatus.NOT_APPLICABLE
        assert result.criteria_relevance["P2.3"] == RelevanceStatus.UNDETERMINED

    def test_preserves_generated_at(self, config_file):
        """generated_at timestamp is stored as-is."""
        result = load_relevance_config(config_file)
        assert result.generated_at == "2025-01-15T10:30:00Z"

    def test_accepts_path_as_string(self, config_file):
        """Function accepts string paths in addition to Path objects."""
        result = load_relevance_config(str(config_file))
        assert isinstance(result, RelevanceConfig)

    def test_empty_services_and_criteria(self, tmp_path):
        """Empty services and criteria dicts are valid."""
        data = {
            "generated_at": "2025-06-01T00:00:00Z",
            "services": {},
            "criteria_relevance": {},
        }
        path = tmp_path / "config.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        result = load_relevance_config(path)
        assert result.services == {}
        assert result.criteria_relevance == {}


class TestLoadRelevanceConfigFileErrors:
    """Tests for file-level errors."""

    def test_file_not_found_raises(self, tmp_path):
        """Non-existent file raises FileNotFoundError."""
        missing = tmp_path / "does-not-exist.json"
        with pytest.raises(FileNotFoundError, match="not found"):
            load_relevance_config(missing)

    def test_invalid_json_raises_value_error(self, tmp_path):
        """Malformed JSON raises ValueError."""
        path = tmp_path / "bad.json"
        path.write_text("{not valid json", encoding="utf-8")
        with pytest.raises(ValueError, match="Invalid JSON"):
            load_relevance_config(path)


class TestLoadRelevanceConfigSchemaValidation:
    """Tests for schema validation failures."""

    def test_missing_services_field(self, tmp_path):
        """Missing 'services' field raises ValueError."""
        data = {
            "generated_at": "2025-01-15T10:30:00Z",
            "criteria_relevance": {},
        }
        path = tmp_path / "config.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        with pytest.raises(ValueError, match="missing required fields.*services"):
            load_relevance_config(path)

    def test_missing_criteria_relevance_field(self, tmp_path):
        """Missing 'criteria_relevance' field raises ValueError."""
        data = {
            "generated_at": "2025-01-15T10:30:00Z",
            "services": {},
        }
        path = tmp_path / "config.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        with pytest.raises(ValueError, match="missing required fields.*criteria_relevance"):
            load_relevance_config(path)

    def test_missing_generated_at_field(self, tmp_path):
        """Missing 'generated_at' field raises ValueError."""
        data = {
            "services": {},
            "criteria_relevance": {},
        }
        path = tmp_path / "config.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        with pytest.raises(ValueError, match="missing required fields.*generated_at"):
            load_relevance_config(path)

    def test_empty_generated_at(self, tmp_path):
        """Empty generated_at string raises ValueError."""
        data = {
            "generated_at": "",
            "services": {},
            "criteria_relevance": {},
        }
        path = tmp_path / "config.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        with pytest.raises(ValueError, match="generated_at"):
            load_relevance_config(path)

    def test_whitespace_only_generated_at(self, tmp_path):
        """Whitespace-only generated_at raises ValueError."""
        data = {
            "generated_at": "   ",
            "services": {},
            "criteria_relevance": {},
        }
        path = tmp_path / "config.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        with pytest.raises(ValueError, match="generated_at"):
            load_relevance_config(path)

    def test_services_not_dict(self, tmp_path):
        """Non-dict services field raises ValueError."""
        data = {
            "generated_at": "2025-01-15T10:30:00Z",
            "services": ["glue", "s3"],
            "criteria_relevance": {},
        }
        path = tmp_path / "config.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        with pytest.raises(ValueError, match="'services' must be an object"):
            load_relevance_config(path)

    def test_service_entry_not_dict(self, tmp_path):
        """Non-dict service entry raises ValueError."""
        data = {
            "generated_at": "2025-01-15T10:30:00Z",
            "services": {"glue": "provisioned"},
            "criteria_relevance": {},
        }
        path = tmp_path / "config.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        with pytest.raises(ValueError, match="Service entry 'glue' must be an object"):
            load_relevance_config(path)

    def test_service_missing_status(self, tmp_path):
        """Service entry without 'status' raises ValueError."""
        data = {
            "generated_at": "2025-01-15T10:30:00Z",
            "services": {"glue": {"confidence": 0.9}},
            "criteria_relevance": {},
        }
        path = tmp_path / "config.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        with pytest.raises(ValueError, match="'glue' is missing required field 'status'"):
            load_relevance_config(path)

    def test_service_missing_confidence(self, tmp_path):
        """Service entry without 'confidence' raises ValueError."""
        data = {
            "generated_at": "2025-01-15T10:30:00Z",
            "services": {"glue": {"status": "provisioned"}},
            "criteria_relevance": {},
        }
        path = tmp_path / "config.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        with pytest.raises(ValueError, match="'glue' is missing required field 'confidence'"):
            load_relevance_config(path)

    def test_service_confidence_not_number(self, tmp_path):
        """Non-numeric confidence raises ValueError."""
        data = {
            "generated_at": "2025-01-15T10:30:00Z",
            "services": {"glue": {"status": "provisioned", "confidence": "high"}},
            "criteria_relevance": {},
        }
        path = tmp_path / "config.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        with pytest.raises(ValueError, match="confidence must be a number"):
            load_relevance_config(path)

    def test_service_confidence_out_of_range_high(self, tmp_path):
        """Confidence > 1.0 raises ValueError."""
        data = {
            "generated_at": "2025-01-15T10:30:00Z",
            "services": {"glue": {"status": "provisioned", "confidence": 1.5}},
            "criteria_relevance": {},
        }
        path = tmp_path / "config.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        with pytest.raises(ValueError, match="confidence must be between 0.0 and 1.0"):
            load_relevance_config(path)

    def test_service_confidence_out_of_range_low(self, tmp_path):
        """Confidence < 0.0 raises ValueError."""
        data = {
            "generated_at": "2025-01-15T10:30:00Z",
            "services": {"glue": {"status": "provisioned", "confidence": -0.1}},
            "criteria_relevance": {},
        }
        path = tmp_path / "config.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        with pytest.raises(ValueError, match="confidence must be between 0.0 and 1.0"):
            load_relevance_config(path)

    def test_criteria_relevance_not_dict(self, tmp_path):
        """Non-dict criteria_relevance raises ValueError."""
        data = {
            "generated_at": "2025-01-15T10:30:00Z",
            "services": {},
            "criteria_relevance": ["P1.1"],
        }
        path = tmp_path / "config.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        with pytest.raises(ValueError, match="'criteria_relevance' must be an object"):
            load_relevance_config(path)

    def test_criteria_invalid_relevance_status(self, tmp_path):
        """Invalid relevance status value raises ValueError."""
        data = {
            "generated_at": "2025-01-15T10:30:00Z",
            "services": {},
            "criteria_relevance": {"P1.1": "invalid-status"},
        }
        path = tmp_path / "config.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        with pytest.raises(ValueError, match="invalid relevance status"):
            load_relevance_config(path)

    def test_non_object_root(self, tmp_path):
        """JSON array at root raises ValueError."""
        path = tmp_path / "config.json"
        path.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
        with pytest.raises(ValueError, match="must be a JSON object"):
            load_relevance_config(path)

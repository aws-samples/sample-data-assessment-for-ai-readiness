"""Unit tests for compute_estate_delta in forge/delta_engine/comparator.py.

Tests cover:
  - Estate-level delta (current vs previous estate score)
  - Per-platform deltas when both assessments have a platform
  - New platform appearing reported as "newly_assessed"
  - Backward compat: falls back to forge_score when estate_score missing
  - Band transitions using estate_band / score_band
"""

import json
from pathlib import Path

import pytest

from forge.delta_engine import (
    EstateDeltaResult,
    PlatformDelta,
    compute_estate_delta,
)


def _write_history(tmp_path: Path, records: list[dict]) -> Path:
    """Write records to a temporary JSONL file."""
    path = tmp_path / "forge_history.jsonl"
    lines = [json.dumps(r) for r in records]
    path.write_text("\n".join(lines) + "\n")
    return path


@pytest.fixture
def single_platform_previous() -> dict:
    """A legacy single-platform (AWS-only) record."""
    return {
        "timestamp": "2026-07-01T10:00:00Z",
        "forge_score": 62.4,
        "score_band": "GOVERNED",
        "pillar_scores": {
            "P1": 70.0, "P2": 55.0, "P3": 60.0, "P4": 65.0,
            "P5": 58.0, "P6": 50.0, "P7": 72.0, "P8": 48.0, "P9": 63.0,
        },
    }


@pytest.fixture
def multi_platform_previous() -> dict:
    """A multi-platform record with AWS only."""
    return {
        "timestamp": "2026-07-01T10:00:00Z",
        "estate_score": 68.5,
        "estate_band": "GOVERNED",
        "platform_scores": {"aws": 68.5},
        "pillar_scores": {
            "P1": 70.0, "P2": 60.0, "P3": 65.0, "P4": 68.0,
            "P5": 62.0, "P6": 55.0, "P7": 75.0, "P8": 50.0, "P9": 66.0,
        },
        "platforms_assessed": ["aws"],
    }


@pytest.fixture
def multi_platform_current() -> dict:
    """A multi-platform record with AWS + Databricks."""
    return {
        "timestamp": "2026-07-15T10:00:00Z",
        "estate_score": 59.8,
        "estate_band": "GOVERNED",
        "platform_scores": {"aws": 72.5, "databricks": 47.2},
        "pillar_scores": {
            "P1": 65.0, "P2": 55.0, "P3": 58.0, "P4": 60.0,
            "P5": 56.0, "P6": 52.0, "P7": 68.0, "P8": 45.0, "P9": 60.0,
        },
        "platforms_assessed": ["aws", "databricks"],
    }


class TestEstateDeltaNotAvailable:
    """Tests for when delta cannot be computed."""

    def test_returns_not_available_for_missing_file(self, tmp_path):
        path = tmp_path / "nonexistent.jsonl"
        result = compute_estate_delta(path)
        assert result.available is False
        assert result.estate_score_delta == 0.0
        assert result.platform_deltas == []
        assert result.new_platforms == []

    def test_returns_not_available_for_single_record(self, tmp_path, multi_platform_previous):
        path = _write_history(tmp_path, [multi_platform_previous])
        result = compute_estate_delta(path)
        assert result.available is False

    def test_returns_not_available_for_empty_file(self, tmp_path):
        path = tmp_path / "empty.jsonl"
        path.write_text("")
        result = compute_estate_delta(path)
        assert result.available is False


class TestEstateScoreDelta:
    """Tests for estate-level score delta computation."""

    def test_computes_estate_score_delta(self, tmp_path, multi_platform_previous, multi_platform_current):
        path = _write_history(tmp_path, [multi_platform_previous, multi_platform_current])
        result = compute_estate_delta(path)
        assert result.available is True
        # 59.8 - 68.5 = -8.7
        assert result.estate_score_delta == -8.7

    def test_falls_back_to_forge_score_when_estate_score_missing(self, tmp_path, single_platform_previous):
        current = {
            "timestamp": "2026-07-15T10:00:00Z",
            "forge_score": 70.0,
            "score_band": "GOVERNED",
            "pillar_scores": {
                "P1": 75.0, "P2": 60.0, "P3": 65.0, "P4": 70.0,
                "P5": 63.0, "P6": 55.0, "P7": 77.0, "P8": 53.0, "P9": 68.0,
            },
        }
        path = _write_history(tmp_path, [single_platform_previous, current])
        result = compute_estate_delta(path)
        assert result.available is True
        # 70.0 - 62.4 = 7.6
        assert result.estate_score_delta == 7.6

    def test_mixed_estate_and_forge_score(self, tmp_path, single_platform_previous, multi_platform_current):
        """Previous has only forge_score, current has estate_score."""
        path = _write_history(tmp_path, [single_platform_previous, multi_platform_current])
        result = compute_estate_delta(path)
        # 59.8 - 62.4 = -2.6
        assert result.estate_score_delta == -2.6


class TestPlatformDeltas:
    """Tests for per-platform delta computation."""

    def test_platform_in_both_assessments_computes_delta(self, tmp_path, multi_platform_previous, multi_platform_current):
        path = _write_history(tmp_path, [multi_platform_previous, multi_platform_current])
        result = compute_estate_delta(path)

        aws_delta = next(d for d in result.platform_deltas if d.platform == "aws")
        # 72.5 - 68.5 = 4.0
        assert aws_delta.delta == 4.0
        assert aws_delta.previous_score == 68.5
        assert aws_delta.current_score == 72.5
        assert aws_delta.status == "improved"

    def test_new_platform_reported_as_newly_assessed(self, tmp_path, multi_platform_previous, multi_platform_current):
        path = _write_history(tmp_path, [multi_platform_previous, multi_platform_current])
        result = compute_estate_delta(path)

        dbx_delta = next(d for d in result.platform_deltas if d.platform == "databricks")
        assert dbx_delta.previous_score is None
        assert dbx_delta.current_score == 47.2
        assert dbx_delta.delta is None
        assert dbx_delta.status == "newly_assessed"

    def test_new_platforms_list_populated(self, tmp_path, multi_platform_previous, multi_platform_current):
        path = _write_history(tmp_path, [multi_platform_previous, multi_platform_current])
        result = compute_estate_delta(path)
        assert "databricks" in result.new_platforms

    def test_no_platform_scores_field_yields_empty_deltas(self, tmp_path, single_platform_previous):
        current = {**single_platform_previous, "forge_score": 70.0, "timestamp": "2026-08-01T10:00:00Z"}
        path = _write_history(tmp_path, [single_platform_previous, current])
        result = compute_estate_delta(path)
        assert result.platform_deltas == []
        assert result.new_platforms == []

    def test_platform_regression_classified_correctly(self, tmp_path):
        previous = {
            "timestamp": "2026-07-01T10:00:00Z",
            "estate_score": 65.0,
            "estate_band": "GOVERNED",
            "platform_scores": {"aws": 72.0, "databricks": 50.0},
            "pillar_scores": {"P1": 65.0, "P2": 60.0, "P3": 60.0, "P4": 60.0, "P5": 60.0, "P6": 60.0, "P7": 60.0, "P8": 60.0, "P9": 60.0},
        }
        current = {
            "timestamp": "2026-07-15T10:00:00Z",
            "estate_score": 60.0,
            "estate_band": "GOVERNED",
            "platform_scores": {"aws": 70.0, "databricks": 45.0},
            "pillar_scores": {"P1": 60.0, "P2": 55.0, "P3": 55.0, "P4": 55.0, "P5": 55.0, "P6": 55.0, "P7": 55.0, "P8": 55.0, "P9": 55.0},
        }
        path = _write_history(tmp_path, [previous, current])
        result = compute_estate_delta(path)

        aws_delta = next(d for d in result.platform_deltas if d.platform == "aws")
        dbx_delta = next(d for d in result.platform_deltas if d.platform == "databricks")
        assert aws_delta.status == "regressed"
        assert aws_delta.delta == -2.0
        assert dbx_delta.status == "regressed"
        assert dbx_delta.delta == -5.0

    def test_platform_unchanged_classified_correctly(self, tmp_path):
        previous = {
            "timestamp": "2026-07-01T10:00:00Z",
            "estate_score": 65.0,
            "estate_band": "GOVERNED",
            "platform_scores": {"aws": 72.0},
            "pillar_scores": {"P1": 65.0, "P2": 60.0, "P3": 60.0, "P4": 60.0, "P5": 60.0, "P6": 60.0, "P7": 60.0, "P8": 60.0, "P9": 60.0},
        }
        current = {
            "timestamp": "2026-07-15T10:00:00Z",
            "estate_score": 65.0,
            "estate_band": "GOVERNED",
            "platform_scores": {"aws": 72.0},
            "pillar_scores": {"P1": 65.0, "P2": 60.0, "P3": 60.0, "P4": 60.0, "P5": 60.0, "P6": 60.0, "P7": 60.0, "P8": 60.0, "P9": 60.0},
        }
        path = _write_history(tmp_path, [previous, current])
        result = compute_estate_delta(path)

        aws_delta = next(d for d in result.platform_deltas if d.platform == "aws")
        assert aws_delta.status == "unchanged"
        assert aws_delta.delta == 0.0


class TestPillarDeltas:
    """Tests for pillar-level delta computation."""

    def test_pillar_deltas_computed(self, tmp_path, multi_platform_previous, multi_platform_current):
        path = _write_history(tmp_path, [multi_platform_previous, multi_platform_current])
        result = compute_estate_delta(path)
        assert len(result.pillar_deltas) == 9
        p1 = next(d for d in result.pillar_deltas if d.pillar == "P1")
        # 65.0 - 70.0 = -5.0
        assert p1.delta == -5.0
        assert p1.classification == "regression"

    def test_improved_and_regressed_counts(self, tmp_path, multi_platform_previous, multi_platform_current):
        path = _write_history(tmp_path, [multi_platform_previous, multi_platform_current])
        result = compute_estate_delta(path)
        # All pillars decreased in this fixture
        assert result.regressed_count > 0


class TestBandTransitions:
    """Tests for band transition detection."""

    def test_detects_band_upgrade(self, tmp_path):
        previous = {
            "timestamp": "2026-07-01T10:00:00Z",
            "estate_score": 49.0,
            "estate_band": "FOUNDATIONAL",
            "platform_scores": {"aws": 49.0},
            "pillar_scores": {"P1": 50.0, "P2": 50.0, "P3": 50.0, "P4": 50.0, "P5": 50.0, "P6": 50.0, "P7": 50.0, "P8": 50.0, "P9": 50.0},
        }
        current = {
            "timestamp": "2026-07-15T10:00:00Z",
            "estate_score": 55.0,
            "estate_band": "GOVERNED",
            "platform_scores": {"aws": 55.0},
            "pillar_scores": {"P1": 55.0, "P2": 55.0, "P3": 55.0, "P4": 55.0, "P5": 55.0, "P6": 55.0, "P7": 55.0, "P8": 55.0, "P9": 55.0},
        }
        path = _write_history(tmp_path, [previous, current])
        result = compute_estate_delta(path)
        assert result.estate_band_transition is not None
        assert result.estate_band_transition.previous_band == "FOUNDATIONAL"
        assert result.estate_band_transition.current_band == "GOVERNED"
        assert result.estate_band_transition.direction == "upgrade"

    def test_no_band_transition_returns_none(self, tmp_path, multi_platform_previous, multi_platform_current):
        # Both are GOVERNED
        path = _write_history(tmp_path, [multi_platform_previous, multi_platform_current])
        result = compute_estate_delta(path)
        assert result.estate_band_transition is None

    def test_falls_back_to_score_band_for_band_transition(self, tmp_path, single_platform_previous):
        current = {
            "timestamp": "2026-07-15T10:00:00Z",
            "forge_score": 80.0,
            "score_band": "AGENT-READY",
            "pillar_scores": {
                "P1": 80.0, "P2": 80.0, "P3": 80.0, "P4": 80.0,
                "P5": 80.0, "P6": 80.0, "P7": 80.0, "P8": 80.0, "P9": 80.0,
            },
        }
        path = _write_history(tmp_path, [single_platform_previous, current])
        result = compute_estate_delta(path)
        assert result.estate_band_transition is not None
        assert result.estate_band_transition.previous_band == "GOVERNED"
        assert result.estate_band_transition.current_band == "AGENT-READY"
        assert result.estate_band_transition.direction == "upgrade"

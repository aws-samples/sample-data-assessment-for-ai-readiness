"""Tests for _generate_estate_remediation_html in dashboard generator."""

import pytest

from forge.dashboard.generator import _generate_estate_remediation_html


def _make_criterion(pillar, index, name, score, platform, relevance_status="RELEVANT"):
    """Helper to build a criterion dict matching segment format."""
    return {
        "pillar": pillar,
        "index": index,
        "name": name,
        "score": score,
        "platform": platform,
        "relevance_status": relevance_status,
        "confidence_score": 0.8,
        "evidence": "Test evidence",
        "criterion_type": "BINARY",
    }


class TestEstateRemediationGrouping:
    """Remediation cards are grouped by platform."""

    def test_groups_by_platform(self):
        segments = [
            {
                "platform": "aws",
                "criteria": [
                    _make_criterion("P1", 1, "Catalog coverage", 0.3, "aws"),
                    _make_criterion("P1", 2, "Schema documented", 0.8, "aws"),  # met
                ],
            },
            {
                "platform": "databricks",
                "criteria": [
                    _make_criterion("P4", 2, "Tables with DQ rules", 0.2, "databricks"),
                    _make_criterion("P4", 5, "Schema enforcement", 0.1, "databricks"),
                ],
            },
        ]
        merged_criteria = []  # Not needed for the function

        result = _generate_estate_remediation_html(merged_criteria, segments)

        # Both platform headers appear
        assert "AWS Remediation" in result
        assert "Databricks Remediation" in result

        # AWS gap is listed
        assert "P1.1: Catalog coverage" in result

        # Met AWS criterion NOT listed
        assert "Schema documented" not in result

        # Databricks gaps listed
        assert "P4.2: Tables with DQ rules" in result
        assert "P4.5: Schema enforcement" in result

    def test_aws_cards_have_aws_styling(self):
        segments = [
            {
                "platform": "aws",
                "criteria": [
                    _make_criterion("P1", 1, "API Access", 0.0, "aws"),
                ],
            },
        ]

        result = _generate_estate_remediation_html([], segments)

        assert "aws-header" in result
        assert "platform-aws" in result

    def test_databricks_cards_have_dbx_styling(self):
        segments = [
            {
                "platform": "databricks",
                "criteria": [
                    _make_criterion("P4", 1, "DLT expectations configured", 0.0, "databricks"),
                ],
            },
        ]

        result = _generate_estate_remediation_html([], segments)

        assert "dbx-header" in result
        assert "platform-dbx" in result


class TestDatabricksServiceReferences:
    """Databricks remediation cards point to specific Databricks features."""

    def test_databricks_criteria_reference_services(self):
        segments = [
            {
                "platform": "databricks",
                "criteria": [
                    _make_criterion("P4", 2, "Tables with DQ rules", 0.2, "databricks"),
                    _make_criterion("P4", 5, "Schema enforcement enabled", 0.1, "databricks"),
                ],
            },
        ]

        result = _generate_estate_remediation_html([], segments)

        # P4.2 maps to delta_live_tables → "Delta Live Tables"
        assert "Delta Live Tables" in result
        # P4.5 maps to delta_lake → "Delta Lake"
        assert "Delta Lake" in result

    def test_p1_criteria_reference_unity_catalog(self):
        segments = [
            {
                "platform": "databricks",
                "criteria": [
                    _make_criterion("P1", 1, "Unity Catalog API queryable", 0.0, "databricks"),
                ],
            },
        ]

        result = _generate_estate_remediation_html([], segments)

        assert "Unity Catalog" in result

    def test_aws_criteria_do_not_reference_databricks_services(self):
        segments = [
            {
                "platform": "aws",
                "criteria": [
                    _make_criterion("P1", 6, "Catalog covers >80%", 0.4, "aws"),
                ],
            },
        ]

        result = _generate_estate_remediation_html([], segments)

        # AWS criteria just show the name, no Databricks service ref
        assert "P1.6: Catalog covers >80%" in result
        assert "Unity Catalog" not in result
        assert "Delta Live Tables" not in result


class TestRelevanceFiltering:
    """Only relevant criteria with score < 0.5 appear."""

    def test_not_applicable_excluded(self):
        segments = [
            {
                "platform": "databricks",
                "criteria": [
                    _make_criterion("P4", 1, "DLT expectations", 0.0, "databricks", "NOT_APPLICABLE"),
                    _make_criterion("P4", 2, "Tables with DQ rules", 0.3, "databricks", "RELEVANT"),
                ],
            },
        ]

        result = _generate_estate_remediation_html([], segments)

        assert "DLT expectations" not in result
        assert "Tables with DQ rules" in result

    def test_met_criteria_excluded(self):
        segments = [
            {
                "platform": "databricks",
                "criteria": [
                    _make_criterion("P4", 1, "DLT expectations", 0.9, "databricks"),
                    _make_criterion("P4", 2, "Tables with DQ rules", 0.3, "databricks"),
                ],
            },
        ]

        result = _generate_estate_remediation_html([], segments)

        # Only unmet (score < 0.5) appears
        assert "DLT expectations" not in result
        assert "Tables with DQ rules" in result

    def test_no_gaps_returns_empty(self):
        segments = [
            {
                "platform": "aws",
                "criteria": [
                    _make_criterion("P1", 1, "API Access", 0.9, "aws"),
                ],
            },
        ]

        result = _generate_estate_remediation_html([], segments)

        assert result == ""


class TestPillarGrouping:
    """Gaps within a platform are grouped by pillar with gap count."""

    def test_pillar_gap_count_shown(self):
        segments = [
            {
                "platform": "databricks",
                "criteria": [
                    _make_criterion("P4", 1, "DLT expectations configured", 0.0, "databricks"),
                    _make_criterion("P4", 2, "Tables with DQ rules", 0.2, "databricks"),
                    _make_criterion("P4", 5, "Schema enforcement", 0.1, "databricks"),
                ],
            },
        ]

        result = _generate_estate_remediation_html([], segments)

        assert "P4: Data Quality (3 gaps)" in result

    def test_multiple_pillars_per_platform(self):
        segments = [
            {
                "platform": "databricks",
                "criteria": [
                    _make_criterion("P1", 1, "UC API queryable", 0.0, "databricks"),
                    _make_criterion("P4", 2, "Tables with DQ rules", 0.2, "databricks"),
                ],
            },
        ]

        result = _generate_estate_remediation_html([], segments)

        assert "P1: Agent Access & Discovery (1 gaps)" in result
        assert "P4: Data Quality (1 gaps)" in result

    def test_max_five_items_per_pillar(self):
        """When more than 5 gaps in a pillar, shows '...and N more'."""
        segments = [
            {
                "platform": "databricks",
                "criteria": [
                    _make_criterion("P1", i, f"Criterion {i}", 0.1, "databricks")
                    for i in range(1, 9)  # 8 gaps
                ],
            },
        ]

        result = _generate_estate_remediation_html([], segments)

        assert "...and 3 more" in result

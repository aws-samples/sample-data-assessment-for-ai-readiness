"""
Tests for the Databricks skill no-document fallback path.

Validates:
  - generate_fallback_prompt() returns proper prompt text
  - process_fallback_response() detects services from free-text
  - generate_full_question_set() returns appropriate questions based on services
"""
from __future__ import annotations

import pytest

from forge.skill_support.databricks_skill import (
    generate_fallback_prompt,
    generate_full_question_set,
    process_fallback_response,
)
from forge.skill_support.databricks_questions import DATABRICKS_QUESTION_BANK


# ---------------------------------------------------------------------------
# generate_fallback_prompt
# ---------------------------------------------------------------------------

class TestGenerateFallbackPrompt:
    """Tests for generate_fallback_prompt()."""

    def test_returns_non_empty_string(self):
        prompt = generate_fallback_prompt()
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_asks_about_services(self):
        prompt = generate_fallback_prompt()
        assert "services" in prompt.lower() or "features" in prompt.lower()

    def test_includes_examples(self):
        prompt = generate_fallback_prompt()
        # Should mention at least a few example services
        assert "Unity Catalog" in prompt
        assert "SQL Warehouse" in prompt


# ---------------------------------------------------------------------------
# process_fallback_response
# ---------------------------------------------------------------------------

class TestProcessFallbackResponse:
    """Tests for process_fallback_response()."""

    def test_empty_response_returns_empty_list(self):
        assert process_fallback_response("") == []
        assert process_fallback_response("   ") == []

    def test_detects_unity_catalog(self):
        services = process_fallback_response("We use Unity Catalog for governance")
        assert "unity_catalog" in services

    def test_detects_uc_abbreviation(self):
        services = process_fallback_response("Our team uses UC extensively")
        assert "unity_catalog" in services

    def test_detects_delta_live_tables(self):
        services = process_fallback_response("Delta Live Tables for all ETL")
        assert "delta_live_tables" in services

    def test_detects_dlt_abbreviation(self):
        services = process_fallback_response("We run DLT pipelines daily")
        assert "delta_live_tables" in services

    def test_detects_sql_warehouse(self):
        services = process_fallback_response("SQL Warehouse is our main query engine")
        assert "sql_warehouse" in services

    def test_detects_mlflow(self):
        services = process_fallback_response("MLflow for experiment tracking")
        assert "mlflow" in services

    def test_detects_structured_streaming(self):
        services = process_fallback_response("Structured Streaming for real-time data")
        assert "structured_streaming" in services

    def test_detects_system_tables(self):
        services = process_fallback_response("We have system tables for audit")
        assert "system_tables" in services

    def test_detects_model_serving(self):
        services = process_fallback_response("Model serving endpoints for inference")
        assert "model_serving" in services

    def test_detects_multiple_services(self):
        response = (
            "We use Unity Catalog, Delta Live Tables, SQL Warehouse, "
            "and MLflow for our data platform."
        )
        services = process_fallback_response(response)
        assert "unity_catalog" in services
        assert "delta_live_tables" in services
        assert "sql_warehouse" in services
        assert "mlflow" in services

    def test_returns_sorted_list(self):
        response = "MLflow, Unity Catalog, Delta Lake"
        services = process_fallback_response(response)
        assert services == sorted(services)

    def test_no_duplicates(self):
        response = "Unity Catalog and UC are the same thing"
        services = process_fallback_response(response)
        assert len(services) == len(set(services))

    def test_no_services_detected(self):
        services = process_fallback_response("We just started and haven't set up anything")
        assert services == []

    def test_case_insensitive(self):
        services = process_fallback_response("unity catalog and DELTA LIVE TABLES")
        assert "unity_catalog" in services
        assert "delta_live_tables" in services


# ---------------------------------------------------------------------------
# generate_full_question_set
# ---------------------------------------------------------------------------

class TestGenerateFullQuestionSet:
    """Tests for generate_full_question_set()."""

    def test_empty_services_returns_all_questions(self):
        questions = generate_full_question_set([])
        assert len(questions) == len(DATABRICKS_QUESTION_BANK)

    def test_filtered_by_services(self):
        # Only unity_catalog — should get questions that require unity_catalog
        questions = generate_full_question_set(["unity_catalog"])
        assert len(questions) > 0
        for q in questions:
            # Each returned question should have at least one service overlapping
            assert "unity_catalog" in q["services"]

    def test_multiple_services_expand_coverage(self):
        uc_only = generate_full_question_set(["unity_catalog"])
        uc_and_dlt = generate_full_question_set(["unity_catalog", "delta_live_tables"])
        # Adding DLT should include more questions
        assert len(uc_and_dlt) >= len(uc_only)

    def test_returns_list_of_dicts_with_expected_keys(self):
        questions = generate_full_question_set(["unity_catalog", "delta_live_tables"])
        for q in questions:
            assert "id" in q
            assert "pillar" in q
            assert "text" in q
            assert "criteria_ids" in q
            assert "services" in q

    def test_all_services_returns_all_questions(self):
        all_services = [
            "unity_catalog", "unity_catalog_lineage", "delta_live_tables",
            "delta_lake", "sql_warehouse", "mlflow", "databricks_workflows",
            "structured_streaming", "system_tables", "model_serving",
        ]
        questions = generate_full_question_set(all_services)
        assert len(questions) == len(DATABRICKS_QUESTION_BANK)

    def test_streaming_only_returns_relevant_questions(self):
        questions = generate_full_question_set(["structured_streaming"])
        for q in questions:
            assert "structured_streaming" in q["services"]

"""
Tests for the Databricks skill flow coordinator.

Validates task 6.4: document parsing integration into skill flow via
get_initial_prompt() and advance_skill_phase().

Requirements validated: 5.2, 5.3, 6.3
"""
from __future__ import annotations

import os
import tempfile

import pytest

from forge.platform_segments.databricks_segment import SkillConversationState
from forge.skill_support.databricks_skill import (
    advance_skill_phase,
    get_initial_prompt,
)


# ---------------------------------------------------------------------------
# get_initial_prompt
# ---------------------------------------------------------------------------


class TestGetInitialPrompt:
    """Tests for the Phase 1 document upload prompt."""

    def test_returns_string(self):
        prompt = get_initial_prompt()
        assert isinstance(prompt, str)

    def test_mentions_cost_usage_summary(self):
        prompt = get_initial_prompt()
        assert "cost usage summary" in prompt

    def test_mentions_architecture_diagrams(self):
        prompt = get_initial_prompt()
        assert "architecture diagrams" in prompt

    def test_mentions_unity_catalog(self):
        prompt = get_initial_prompt()
        assert "Unity Catalog" in prompt


# ---------------------------------------------------------------------------
# advance_skill_phase — document_upload phase
# ---------------------------------------------------------------------------


class TestPhaseDocumentUpload:
    """Tests for the document_upload → document_review transition."""

    def test_no_files_transitions_to_document_review(self):
        state = SkillConversationState()
        state, msg = advance_skill_phase(state, file_paths=None)
        assert state.phase == "document_review"

    def test_no_files_returns_fallback_prompt(self):
        state = SkillConversationState()
        state, msg = advance_skill_phase(state, file_paths=None)
        assert "services" in msg.lower() or "features" in msg.lower()

    def test_with_csv_transitions_to_document_review(self):
        csv_content = "service,spend_30d,compute_hours\nsql_warehouse,500.00,100\n"
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False
        ) as f:
            f.write(csv_content)
            csv_path = f.name

        try:
            state = SkillConversationState()
            state, msg = advance_skill_phase(state, file_paths=[csv_path])
            assert state.phase == "document_review"
        finally:
            os.unlink(csv_path)

    def test_with_csv_identifies_services(self):
        csv_content = (
            "service,spend_30d,compute_hours\n"
            "sql_warehouse,500.00,100\n"
            "delta_live_tables,300.00,50\n"
        )
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False
        ) as f:
            f.write(csv_content)
            csv_path = f.name

        try:
            state = SkillConversationState()
            state, msg = advance_skill_phase(state, file_paths=[csv_path])
            assert "sql_warehouse" in state.services_identified
            # Cost parser identifies services from the CSV rows
            assert len(state.services_identified) >= 2
        finally:
            os.unlink(csv_path)

    def test_with_csv_stores_documents_uploaded(self):
        csv_content = "service,spend_30d,compute_hours\nsql_warehouse,500.00,100\n"
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False
        ) as f:
            f.write(csv_content)
            csv_path = f.name

        try:
            state = SkillConversationState()
            state, msg = advance_skill_phase(state, file_paths=[csv_path])
            assert csv_path in state.documents_uploaded
        finally:
            os.unlink(csv_path)

    def test_review_message_contains_summary(self):
        csv_content = "service,spend_30d,compute_hours\nsql_warehouse,500.00,100\n"
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False
        ) as f:
            f.write(csv_content)
            csv_path = f.name

        try:
            state = SkillConversationState()
            state, msg = advance_skill_phase(state, file_paths=[csv_path])
            assert "correct" in msg.lower() or "corrections" in msg.lower()
        finally:
            os.unlink(csv_path)


# ---------------------------------------------------------------------------
# advance_skill_phase — document_review phase
# ---------------------------------------------------------------------------


class TestPhaseDocumentReview:
    """Tests for the document_review → follow_up transition."""

    def test_with_services_transitions_to_follow_up(self):
        state = SkillConversationState(
            phase="document_review",
            services_identified=["unity_catalog", "delta_live_tables"],
        )
        state, msg = advance_skill_phase(state, user_response="Looks correct")
        assert state.phase in ("follow_up", "complete")

    def test_no_services_extracts_from_response(self):
        state = SkillConversationState(phase="document_review")
        state, msg = advance_skill_phase(
            state, user_response="We use Unity Catalog and MLflow"
        )
        assert "unity_catalog" in state.services_identified
        assert "mlflow" in state.services_identified

    def test_generates_followup_questions(self):
        state = SkillConversationState(
            phase="document_review",
            services_identified=["unity_catalog", "delta_live_tables"],
        )
        state, msg = advance_skill_phase(state, user_response="Confirmed")
        if state.phase == "follow_up":
            assert len(state.pending_questions) > 0

    def test_all_criteria_scored_skips_to_complete(self):
        # If all criteria already scored from documents, skip follow-up
        from forge.platform_segments.databricks_registry import (
            DATABRICKS_CRITERIA_REGISTRY,
        )

        # Score every criterion for unity_catalog
        state = SkillConversationState(
            phase="document_review",
            services_identified=["unity_catalog"],
        )
        for crit in DATABRICKS_CRITERIA_REGISTRY:
            crit_key = f"{crit.pillar}.{crit.index}"
            state.criteria_scored[crit_key] = 1.0
            state.criteria_evidence[crit_key] = "Pre-filled"
            state.criteria_confidence[crit_key] = 0.8

        state, msg = advance_skill_phase(state, user_response="Correct")
        assert state.phase == "complete"
        assert "ready" in msg.lower()


# ---------------------------------------------------------------------------
# advance_skill_phase — follow_up phase
# ---------------------------------------------------------------------------


class TestPhaseFollowUp:
    """Tests for the follow_up → complete transition."""

    def test_answering_scores_criterion(self):
        state = SkillConversationState(
            phase="follow_up",
            services_identified=["unity_catalog"],
            pending_questions=[
                {
                    "criterion_key": "P1.1",
                    "pillar": "P1",
                    "text": "Is UC API accessible?",
                    "criteria_ids": ["P1.1"],
                }
            ],
        )
        state, msg = advance_skill_phase(state, user_response="Yes, fully configured")
        assert "P1.1" in state.criteria_scored
        assert state.criteria_scored["P1.1"] == 1.0

    def test_negative_answer_scores_zero(self):
        state = SkillConversationState(
            phase="follow_up",
            services_identified=["unity_catalog"],
            pending_questions=[
                {
                    "criterion_key": "P1.1",
                    "pillar": "P1",
                    "text": "Is UC API accessible?",
                    "criteria_ids": ["P1.1"],
                }
            ],
        )
        state, msg = advance_skill_phase(state, user_response="No, we don't have that")
        assert state.criteria_scored["P1.1"] == 0.0

    def test_last_question_completes(self):
        state = SkillConversationState(
            phase="follow_up",
            services_identified=["unity_catalog"],
            pending_questions=[
                {
                    "criterion_key": "P1.1",
                    "pillar": "P1",
                    "text": "Is UC API accessible?",
                    "criteria_ids": ["P1.1"],
                }
            ],
        )
        state, msg = advance_skill_phase(state, user_response="Yes")
        assert state.phase == "complete"
        assert "ready" in msg.lower()

    def test_multiple_questions_pops_one_at_a_time(self):
        state = SkillConversationState(
            phase="follow_up",
            services_identified=["unity_catalog"],
            pending_questions=[
                {
                    "criterion_key": "P1.1",
                    "pillar": "P1",
                    "text": "Question 1?",
                    "criteria_ids": ["P1.1"],
                },
                {
                    "criterion_key": "P1.2",
                    "pillar": "P1",
                    "text": "Question 2?",
                    "criteria_ids": ["P1.2"],
                },
            ],
        )
        state, msg = advance_skill_phase(state, user_response="Yes")
        assert state.phase == "follow_up"
        assert len(state.pending_questions) == 1
        assert "Question 2?" in msg

    def test_percentage_response_scores_analog(self):
        state = SkillConversationState(
            phase="follow_up",
            services_identified=["unity_catalog"],
            pending_questions=[
                {
                    "criterion_key": "P1.2",
                    "pillar": "P1",
                    "text": "What percentage?",
                    "criteria_ids": ["P1.2"],
                }
            ],
        )
        state, msg = advance_skill_phase(state, user_response="About 75%")
        assert state.criteria_scored["P1.2"] == 0.75


# ---------------------------------------------------------------------------
# End-to-end flow
# ---------------------------------------------------------------------------


class TestEndToEndFlow:
    """Tests for full skill flow from start to finish."""

    def test_no_docs_flow_completes(self):
        state = SkillConversationState()

        # Phase 1: no docs
        state, msg = advance_skill_phase(state, file_paths=None)
        assert state.phase == "document_review"

        # Phase 2: tell services
        state, msg = advance_skill_phase(
            state, user_response="Unity Catalog and Delta Live Tables"
        )
        assert state.phase in ("follow_up", "complete")

        # Phase 3: answer all questions
        max_iterations = 50
        while state.phase == "follow_up" and max_iterations > 0:
            state, msg = advance_skill_phase(state, user_response="Yes, we have that")
            max_iterations -= 1

        assert state.phase == "complete"
        assert len(state.criteria_scored) > 0

    def test_complete_phase_returns_assessment_ready(self):
        state = SkillConversationState(phase="complete")
        state, msg = advance_skill_phase(state, user_response="anything")
        assert "complete" in msg.lower() or "Assessment" in msg

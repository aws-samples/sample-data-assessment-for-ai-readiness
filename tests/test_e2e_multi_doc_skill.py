"""
End-to-end test: Databricks skill with BOTH billing CSV + architecture doc.

Demonstrates the full document-first assessment flow with realistic inputs:
  - system.billing.usage CSV export → identifies active services
  - Workspace architecture description → pre-fills criterion evidence

This results in fewer follow-up questions and a higher-fidelity score.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from forge.platform_segments.databricks_segment import (
    SkillConversationState,
    build_databricks_segment,
)
from forge.skill_support.databricks_skill import (
    advance_skill_phase,
    get_initial_prompt,
    parse_uploaded_documents,
    summarize_findings,
)
from forge.profile_engine import ForgeProfile
from forge.profile_engine.dimensions import (
    AgentMaturity,
    Architecture,
    Industry,
    Workload,
)
from forge.models import PlatformSegment, RelevanceStatus


FIXTURE_DIR = Path(__file__).parent / "fixtures"
BILLING_CSV = str(FIXTURE_DIR / "databricks_billing_usage.csv")
ARCH_DOC = str(FIXTURE_DIR / "databricks_workspace_description.txt")


@pytest.fixture
def test_profile() -> ForgeProfile:
    return ForgeProfile(
        architecture=Architecture.HYBRID,
        workload=Workload.MULTI_TOOL_AGENTS,
        industry=Industry.FINANCIAL_SERVICES,
        agent_maturity=AgentMaturity.SINGLE_AGENT_PROD,
    )


class TestMultiDocumentSkillFlow:
    """Full skill flow with billing CSV + architecture document."""

    def test_both_docs_parsed_together(self):
        """Uploading both documents identifies more services and pre-fills criteria."""
        services, evidence = parse_uploaded_documents([BILLING_CSV, ARCH_DOC])

        print(f"\n=== Services Identified ===")
        for svc in sorted(services):
            print(f"  • {svc}")

        print(f"\n=== Evidence Extracted ({len(evidence)} items) ===")
        for ev in evidence:
            print(f"  {ev.criterion_id}: {ev.evidence} (conf={ev.confidence:.0%})")

        # Billing CSV identifies active services
        assert "sql_warehouse" in services
        assert "databricks_workflows" in services
        assert "delta_live_tables" in services

        # Architecture doc adds services via evidence inference
        assert "unity_catalog" in services  # mentioned in the doc
        assert len(evidence) > 10  # Lots of criteria evidence from the arch doc

    def test_full_flow_with_both_documents(self, test_profile):
        """Complete flow: upload both docs → review → few follow-ups → segment."""
        state = SkillConversationState()

        # Phase 1: Upload both documents
        state, msg = advance_skill_phase(state, file_paths=[BILLING_CSV, ARCH_DOC])

        print(f"\n{'='*60}")
        print(f"PHASE 1 → DOCUMENT REVIEW")
        print(f"{'='*60}")
        print(f"Services: {state.services_identified}")
        print(f"Criteria pre-filled: {len(state.criteria_scored)}")
        print(f"\nMessage:\n{msg}")

        assert state.phase == "document_review"
        assert len(state.services_identified) >= 6
        # Architecture doc should pre-fill some criteria
        assert len(state.criteria_scored) > 0

        # Phase 2: Confirm findings
        state, msg = advance_skill_phase(
            state,
            user_response="Looks correct!"
        )

        print(f"\n{'='*60}")
        print(f"PHASE 2 → FOLLOW-UP QUESTIONS")
        print(f"{'='*60}")
        print(f"Pending questions: {len(state.pending_questions)}")
        print(f"\nMessage:\n{msg}")

        # Phase 3: Answer remaining follow-ups
        question_count = 0
        while state.phase == "follow_up" and question_count < 25:
            # Give positive answers
            answer = "Yes, that's fully configured and active"
            print(f"\n  Q{question_count + 1}: {msg}")
            print(f"  A: {answer}")
            state, msg = advance_skill_phase(state, user_response=answer)
            question_count += 1

        print(f"\n{'='*60}")
        print(f"SKILL COMPLETE")
        print(f"{'='*60}")
        print(f"Phase: {state.phase}")
        print(f"Total questions answered: {question_count}")
        print(f"Total criteria scored: {len(state.criteria_scored)}")

        assert state.phase == "complete"

        # Build the segment
        segment = build_databricks_segment(state, test_profile)

        print(f"\n{'='*60}")
        print(f"DATABRICKS PLATFORM SEGMENT")
        print(f"{'='*60}")
        print(f"FORGE Score: {segment.summary['forge_score']:.1f}")
        print(f"Readiness Band: {segment.summary['readiness_band']}")
        print(f"Raw Score: {segment.summary['raw_score']:.2f}")
        print(f"Coverage Multiplier: {segment.summary['coverage_multiplier']:.4f}")

        print(f"\nPillar Breakdown:")
        for pillar in segment.pillars:
            print(f"  {pillar.code} ({pillar.name}): {pillar.raw_score:.1f}% "
                  f"[{pillar.relevant_count} relevant, {pillar.not_applicable_count} N/A]")

        # Count criteria by status
        relevant = [c for c in segment.criteria if c.relevance_status == RelevanceStatus.RELEVANT]
        na = [c for c in segment.criteria if c.relevance_status == RelevanceStatus.NOT_APPLICABLE]
        undetermined = [c for c in segment.criteria if c.relevance_status == RelevanceStatus.UNDETERMINED]

        print(f"\nCriteria Status:")
        print(f"  Relevant (scored): {len(relevant)}")
        print(f"  Not Applicable: {len(na)}")
        print(f"  Undetermined: {len(undetermined)}")

        # Assertions
        assert isinstance(segment, PlatformSegment)
        assert segment.platform == "databricks"
        assert segment.summary["forge_score"] > 0
        # With both docs + positive answers, should be a reasonable score
        assert segment.summary["forge_score"] > 30  # Should get above UNREADY

        return segment

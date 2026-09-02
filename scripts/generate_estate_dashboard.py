#!/usr/bin/env python3
"""
Generate a multi-platform estate dashboard using:
  - Past AWS assessment results (no re-probe)
  - Databricks skill output from fixture documents

Produces: forge_output/forge_estate_dashboard.html
"""
import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from forge.models import (
    CriterionResult,
    CriterionType,
    ForgeAssessmentResult,
    PillarScore,
    PlatformSegment,
    RelevanceStatus,
    ReadinessBand,
)
from forge.platform_segments.aws_adapter import wrap_aws_result
from forge.platform_segments.databricks_segment import (
    SkillConversationState,
    build_databricks_segment,
)
from forge.scoring_engine.merge import merge_criteria, compute_estate_score
from forge.scoring_engine.merge import _build_pillar_scores_from_merged
from forge.skill_support.databricks_skill import (
    advance_skill_phase,
    parse_uploaded_documents,
)
from forge.profile_engine import ForgeProfile, load_profile, resolve_profile
from forge.profile_engine.dimensions import (
    AgentMaturity,
    Architecture,
    Industry,
    Workload,
)


# ─── Paths ─────────────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).parent.parent
PROFILE_PATH = PROJECT_ROOT / "forge_output" / "forge_profile.yaml"
BILLING_CSV = PROJECT_ROOT / "tests" / "fixtures" / "databricks_billing_usage.csv"
ARCH_DOC = PROJECT_ROOT / "tests" / "fixtures" / "databricks_workspace_description.txt"
OUTPUT_DIR = PROJECT_ROOT / "forge_output"


def _find_latest_aws_assessment() -> Path:
    """Find the most recent AWS assessment JSON file.

    Looks for files matching forge_assessment_*.json (excluding estate files)
    in the assessments directory and returns the most recent by filename timestamp.
    Falls back to forge_assessment_results.json if no timestamped files exist.
    """
    assessments_dir = PROJECT_ROOT / "forge_output" / "assessments"
    candidates = sorted(
        [f for f in assessments_dir.glob("forge_assessment_*.json")
         if "estate" not in f.name and f.name != "forge_assessment_results.json"],
        reverse=True,
    )
    if candidates:
        return candidates[0]
    # Fallback: non-timestamped results file
    fallback = assessments_dir / "forge_assessment_results.json"
    if fallback.exists():
        return fallback
    raise FileNotFoundError(
        f"No AWS assessment files found in {assessments_dir}. "
        "Run the AWS assessment first."
    )


AWS_ASSESSMENT = _find_latest_aws_assessment()


def load_aws_segment() -> PlatformSegment:
    """Load past AWS assessment and wrap as PlatformSegment."""
    print("📦 Loading past AWS assessment...")
    with open(AWS_ASSESSMENT) as f:
        data = json.load(f)

    # Use from_dict for clean deserialization, then wrap as segment
    result = ForgeAssessmentResult.from_dict(data)
    segment = wrap_aws_result(result)
    print(f"   AWS Score: {segment.summary['forge_score']} ({segment.summary['readiness_band']})")
    print(f"   Criteria: {len(segment.criteria)}")
    return segment


def run_databricks_skill() -> PlatformSegment:
    """Load Databricks skill state from disk, or fall back to fixture documents.

    Priority:
      1. Saved session state (forge_output/databricks_skill_state.json) — from a
         real skill conversation.
      2. Fixture documents (tests/fixtures/) — for demo/testing.
    """
    profile = load_profile(PROFILE_PATH)
    state_path = PROJECT_ROOT / "forge_output" / "databricks_skill_state.json"

    if state_path.exists():
        print("\n🧱 Loading Databricks skill state from saved session...")
        state = SkillConversationState.load(state_path)
        print(f"   Services identified: {len(state.services_identified)}")
        print(f"   Criteria scored: {len(state.criteria_scored)}")
    else:
        print("\n🧱 Running Databricks skill (fixture documents)...")
        state = SkillConversationState()

        # Phase 1: Upload both documents
        state, msg = advance_skill_phase(state, file_paths=[str(BILLING_CSV), str(ARCH_DOC)])
        print(f"   Services identified: {len(state.services_identified)}")
        print(f"   Criteria pre-filled from docs: {len(state.criteria_scored)}")

        # Phase 2: Confirm findings
        state, msg = advance_skill_phase(state, user_response="Looks correct, all confirmed.")

        # Phase 3: Answer follow-up questions positively
        question_count = 0
        positive_answers = [
            "Yes, about 92% of all tables are in Unity Catalog",
            "Around 85% of production tables have lineage captured",
            "About 80% of production tables have DQ monitors",
            "Yes, Structured Streaming is actively processing events",
            "About 90% have scheduled freshness SLAs",
            "Yes, fully configured",
            "About 75%",
            "Yes",
            "Approximately 88%",
            "Yes, all configured and active",
        ]
        while state.phase == "follow_up" and question_count < 15:
            answer = positive_answers[question_count % len(positive_answers)]
            state, msg = advance_skill_phase(state, user_response=answer)
            question_count += 1

        print(f"   Follow-up questions answered: {question_count}")
        print(f"   Total criteria scored: {len(state.criteria_scored)}")

    # Build the segment
    segment = build_databricks_segment(state, profile)
    print(f"   Databricks Score: {segment.summary['forge_score']} ({segment.summary['readiness_band']})")
    return segment


def compute_estate(aws_segment: PlatformSegment, dbx_segment: PlatformSegment):
    """Merge segments and compute estate score."""
    print("\n🔗 Merging platform segments into estate score...")
    profile = load_profile(PROFILE_PATH)
    resolved = resolve_profile(profile)

    merged_criteria = merge_criteria([aws_segment, dbx_segment])
    estate_score, estate_band, raw_score, coverage_mult = compute_estate_score(
        merged_criteria,
        resolved.effective_weights,
        resolved.effective_floors,
    )
    merged_pillars = _build_pillar_scores_from_merged(merged_criteria)

    print(f"   Estate Score: {estate_score} ({estate_band.value})")
    print(f"   Raw Score: {raw_score:.2f}")
    print(f"   Coverage Multiplier: {coverage_mult:.4f}")
    print(f"   Merged criteria: {len(merged_criteria)}")

    return estate_score, estate_band, raw_score, coverage_mult, merged_criteria, merged_pillars


def generate_dashboard(
    aws_segment, dbx_segment,
    estate_score, estate_band, raw_score, coverage_mult,
    merged_criteria, merged_pillars,
):
    """Generate the HTML estate dashboard."""
    from forge.dashboard.generator import (
        _generate_gauge_svg,
        _generate_radar_svg,
        _generate_radar_toggle_section,
        _generate_platform_badges,
        _generate_estate_criteria_html,
        _generate_estate_remediation_html,
    )

    profile = load_profile(PROFILE_PATH)
    resolved = resolve_profile(profile)

    # ─── Build data structures for the dashboard ───────────────────────────
    pillar_codes = ["P1", "P2", "P3", "P4", "P5", "P6", "P7", "P8", "P9"]

    # Combined (estate) pillar scores
    combined_scores = {p.code: p.raw_score for p in merged_pillars}

    # Per-platform pillar scores
    aws_pillar_map = {p.code: p.raw_score for p in aws_segment.pillars}
    dbx_pillar_map = {p.code: p.raw_score for p in dbx_segment.pillars}

    platform_scores = {
        "aws": aws_pillar_map,
        "databricks": dbx_pillar_map,
    }

    # Segments data for criteria/remediation
    segments_data = [
        {
            "platform": "aws",
            "forge_score": aws_segment.summary["forge_score"],
            "score_band": aws_segment.summary.get("readiness_band", "FOUNDATIONAL"),
            "criteria": [
                {
                    "pillar": c.pillar,
                    "index": c.index,
                    "name": c.name,
                    "score": c.score,
                    "relevance_status": c.relevance_status.value if hasattr(c.relevance_status, 'value') else str(c.relevance_status),
                    "confidence_score": c.confidence_score,
                    "evidence": c.evidence,
                    "criterion_type": c.criterion_type.value if hasattr(c.criterion_type, 'value') else str(c.criterion_type),
                    "platform": "aws",
                    "analog_detail": {"numerator": c.analog_detail.numerator, "denominator": c.analog_detail.denominator} if c.analog_detail else None,
                }
                for c in aws_segment.criteria
            ],
        },
        {
            "platform": "databricks",
            "forge_score": dbx_segment.summary["forge_score"],
            "score_band": dbx_segment.summary.get("readiness_band", "FOUNDATIONAL"),
            "criteria": [
                {
                    "pillar": c.pillar,
                    "index": c.index,
                    "name": c.name,
                    "score": c.score,
                    "relevance_status": c.relevance_status.value if hasattr(c.relevance_status, 'value') else str(c.relevance_status),
                    "confidence_score": c.confidence_score,
                    "evidence": c.evidence,
                    "criterion_type": c.criterion_type.value if hasattr(c.criterion_type, 'value') else str(c.criterion_type),
                    "platform": "databricks",
                    "analog_detail": {"numerator": c.analog_detail.numerator, "denominator": c.analog_detail.denominator} if c.analog_detail else None,
                }
                for c in dbx_segment.criteria
            ],
        },
    ]

    merged_criteria_data = [
        {
            "pillar": c.pillar,
            "index": c.index,
            "name": c.name,
            "score": c.score,
            "relevance_status": c.relevance_status.value,
            "confidence_score": c.confidence_score,
            "evidence": c.evidence,
            "criterion_type": c.criterion_type.value,
            "platform": "estate",
            "pillar_name": c.name,
        }
        for c in merged_criteria
    ]

    # ─── Generate dashboard HTML ──────────────────────────────────────────

    # Band colors
    band_colors = {
        "UNREADY": "#dc3545",
        "FOUNDATIONAL": "#fd7e14",
        "GOVERNED": "#ffc107",
        "AGENT-READY": "#28a745",
        "FORGE-NATIVE": "#007bff",
    }
    band_color = band_colors.get(estate_band.value, "#6c757d")

    # Generate components
    gauge_svg = _generate_gauge_svg(estate_score)
    radar_section = _generate_radar_toggle_section(combined_scores, platform_scores, pillar_codes)
    platform_badges = _generate_platform_badges(segments_data)
    criteria_html = _generate_estate_criteria_html(merged_criteria_data, segments_data)
    remediation_html = _generate_estate_remediation_html(merged_criteria_data, segments_data)

    # Pillar bar charts
    pillar_bars_html = ""
    for code in pillar_codes:
        score = combined_scores.get(code, 0.0)
        color = "#dc3545" if score < 25 else "#fd7e14" if score < 50 else "#ffc107" if score < 75 else "#28a745"
        pillar_bars_html += f'''      <div class="pillar-bar">
        <span class="pillar-label">{code}</span>
        <div class="bar-bg"><div class="bar-fill" style="width:{score:.0f}%;background:{color}"></div></div>
        <span class="bar-value" style="color:{color}">{score:.0f}%</span>
      </div>\n'''

    # Profile display
    profile_display = (
        f"Architecture: <strong>{profile.architecture.value}</strong> | "
        f"Workload: <strong>{profile.workload.value}</strong> | "
        f"Industry: <strong>{profile.industry.value}</strong> | "
        f"Agent Maturity: <strong>{profile.agent_maturity.value}</strong>"
    )

    # ─── Assemble full HTML ────────────────────────────────────────────────
    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>FORGE Estate Assessment — Multi-Platform Dashboard</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
       background: #0d1117; color: #c9d1d9; line-height: 1.6; }}
.container {{ max-width: 1400px; margin: 0 auto; padding: 20px; }}
header {{ background: linear-gradient(135deg, #161b22 0%, #1c2128 100%);
         border: 1px solid #30363d; border-radius: 12px; padding: 30px;
         margin-bottom: 24px; }}
h1 {{ color: #f0f6fc; font-size: 28px; margin-bottom: 8px; }}
h2 {{ color: #f0f6fc; font-size: 20px; margin-bottom: 16px; border-bottom: 1px solid #30363d; padding-bottom: 8px; }}
h3 {{ color: #e6edf3; font-size: 16px; margin-bottom: 12px; }}
.meta {{ color: #8b949e; font-size: 14px; }}
.score-hero {{ display: flex; align-items: center; gap: 40px; margin-top: 20px; flex-wrap: wrap; }}
.score-number {{ font-size: 72px; font-weight: 800; color: {band_color}; }}
.band-badge {{ background: {band_color}; color: #fff; padding: 8px 20px;
              border-radius: 20px; font-weight: 700; font-size: 18px; }}
.score-details {{ color: #8b949e; font-size: 13px; margin-top: 8px; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(400px, 1fr)); gap: 20px; margin-bottom: 24px; }}
.card {{ background: #161b22; border: 1px solid #30363d; border-radius: 12px; padding: 24px; }}
.pillar-bar {{ display: flex; align-items: center; gap: 12px; margin: 8px 0; }}
.pillar-label {{ width: 40px; font-size: 13px; color: #8b949e; font-weight: 600; }}
.bar-bg {{ flex: 1; height: 24px; background: #21262d; border-radius: 4px; overflow: hidden; }}
.bar-fill {{ height: 100%; border-radius: 4px; transition: width 0.8s ease; }}
.bar-value {{ width: 50px; text-align: right; font-weight: 600; font-size: 13px; }}
.platform-badges {{ display: flex; gap: 16px; margin-top: 16px; flex-wrap: wrap; }}
.platform-badge {{ display: flex; align-items: center; gap: 10px; background: #161b22;
                   border: 1px solid #30363d; border-radius: 8px; padding: 10px 18px; }}
.platform-badge .platform-name {{ font-weight: 700; font-size: 13px; color: #8b949e; }}
.platform-badge .platform-score {{ font-weight: 800; font-size: 20px; color: #c9d1d9; }}
.platform-badge .platform-band {{ color: #fff; padding: 3px 10px; border-radius: 12px;
                                   font-weight: 600; font-size: 11px; }}
.radar-toggle {{ display: flex; gap: 4px; margin-bottom: 12px; }}
.radar-btn {{ padding: 6px 14px; background: #21262d; border: 1px solid #30363d;
             border-radius: 6px; cursor: pointer; font-size: 12px; color: #8b949e; border: 1px solid #30363d; }}
.radar-btn.active {{ background: #388bfd22; border-color: #388bfd; color: #58a6ff; }}
.radar-view {{ display: none; }}
.radar-view.active {{ display: block; }}
.tabs {{ display: flex; gap: 4px; margin-bottom: 16px; flex-wrap: wrap; }}
.tab {{ padding: 8px 16px; background: #21262d; border: 1px solid #30363d;
       border-radius: 6px; cursor: pointer; font-size: 13px; color: #8b949e; }}
.tab.active {{ background: #388bfd22; border-color: #388bfd; color: #58a6ff; }}
.criteria-table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
.criteria-table th {{ background: #21262d; padding: 10px; text-align: left; color: #8b949e; }}
.criteria-table td {{ padding: 8px 10px; border-bottom: 1px solid #21262d; }}
.criteria-table tr.met td {{ color: #c9d1d9; }}
.criteria-table tr.unmet td {{ color: #f85149; }}
.evidence {{ max-width: 300px; font-size: 12px; color: #8b949e; }}
.confidence {{ background: #21262d; padding: 2px 8px; border-radius: 10px; font-size: 11px; }}
.platform-tag {{ padding: 2px 6px; border-radius: 4px; font-size: 10px; font-weight: 600; display: inline-block; margin: 1px 2px; }}
.platform-tag.aws {{ background: #ff990022; color: #ff9900; border: 1px solid #ff990044; }}
.platform-tag.dbx {{ background: #ff383822; color: #ff3838; border: 1px solid #ff383844; }}
.platform-tag.estate {{ background: #388bfd22; color: #58a6ff; border: 1px solid #388bfd44; }}
.remediation-card {{ background: #1c1f26; border-left: 3px solid #f0883e;
                    padding: 16px; margin: 8px 0; border-radius: 0 8px 8px 0; }}
.remediation-card h4 {{ color: #f0883e; margin-bottom: 8px; font-size: 14px; }}
.remediation-card li {{ margin-left: 20px; font-size: 13px; color: #8b949e; }}
.platform-header {{ margin-top: 16px; margin-bottom: 8px; font-size: 16px; }}
.platform-header .platform-icon {{ margin-right: 4px; }}
.aws-header {{ color: #ff9900; }}
.dbx-header {{ color: #ff3838; }}
.remediation-card.platform-aws {{ border-left-color: #ff9900; }}
.remediation-card.platform-dbx {{ border-left-color: #ff3838; }}
.pillar-detail {{ display: none; }}
.pillar-detail.active {{ display: block; }}
@media (max-width: 768px) {{
  .grid {{ grid-template-columns: 1fr; }}
  .score-hero {{ flex-direction: column; gap: 16px; }}
}}
</style>
</head>
<body>
<div class="container">
  <header>
    <h1>🔥 FORGE Estate Assessment — Multi-Platform Dashboard</h1>
    <p class="meta">
      Platforms: <strong>AWS + Databricks</strong> |
      Date: <strong>2026-07-20</strong> |
      Profile: {profile_display}
    </p>
    <div class="score-hero">
      <div>
        <div class="score-number">{estate_score}</div>
        <span class="band-badge">{estate_band.value}</span>
        <div class="score-details">
          Raw Score: {raw_score:.2f} | Coverage Multiplier: {coverage_mult:.4f}
        </div>
      </div>
      <div>{gauge_svg}</div>
    </div>
    {platform_badges}
  </header>

  <div class="grid">
    <div class="card">
      <h2>Estate Pillar Scores (Combined)</h2>
{pillar_bars_html}
    </div>
    <div class="card">
      <h2>Score Radar</h2>
      {radar_section}
    </div>
  </div>

  <div class="card" style="margin-bottom:24px">
    <h2>Criteria Detail (Estate View)</h2>
    <div class="tabs">
'''

    # Add pillar tabs
    for code in pillar_codes:
        html += f'      <div class="tab" onclick="showPillar(\'{code}\')" id="tab-{code}">{code}</div>\n'

    html += f'''    </div>
    <div id="criteria-panels">
      {criteria_html}
    </div>
  </div>

  <div class="card">
    <h2>Remediation Roadmap (by Platform)</h2>
    {remediation_html}
  </div>

</div>

<script>
function showPillar(code) {{
  document.querySelectorAll('.pillar-detail').forEach(el => el.style.display = 'none');
  document.querySelectorAll('.tab').forEach(el => el.classList.remove('active'));
  var el = document.getElementById('detail-' + code);
  if (el) {{ el.style.display = 'block'; }}
  var tab = document.getElementById('tab-' + code);
  if (tab) {{ tab.classList.add('active'); }}
}}
showPillar('P1');
</script>
</body>
</html>'''

    # Write output
    output_path = OUTPUT_DIR / "forge_estate_dashboard.html"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        f.write(html)

    print(f"\n✅ Dashboard generated: {output_path}")
    print(f"   Open in browser: file://{output_path.resolve()}")


def main():
    print("=" * 60)
    print("FORGE Estate Assessment — Multi-Platform (AWS + Databricks)")
    print("=" * 60)

    # Step 1: Load past AWS results
    aws_segment = load_aws_segment()

    # Step 2: Run Databricks skill
    dbx_segment = run_databricks_skill()

    # Step 3: Compute estate score
    estate_score, estate_band, raw_score, coverage_mult, merged_criteria, merged_pillars = \
        compute_estate(aws_segment, dbx_segment)

    # Step 4: Generate dashboard
    print("\n📊 Generating estate dashboard...")
    generate_dashboard(
        aws_segment, dbx_segment,
        estate_score, estate_band, raw_score, coverage_mult,
        merged_criteria, merged_pillars,
    )

    # Summary
    print(f"\n{'=' * 60}")
    print(f"ESTATE SUMMARY")
    print(f"{'=' * 60}")
    print(f"  AWS Score:        {aws_segment.summary['forge_score']} ({aws_segment.summary['readiness_band']})")
    print(f"  Databricks Score: {dbx_segment.summary['forge_score']} ({dbx_segment.summary['readiness_band']})")
    print(f"  Estate Score:     {estate_score} ({estate_band.value})")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()

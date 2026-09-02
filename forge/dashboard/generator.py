#!/usr/bin/env python3
"""
FORGE 2.3 Dashboard Generator
Takes assessment JSON and produces an interactive HTML dashboard.
Uses pure inline SVG for all charts — zero external dependencies.

Usage:
  python3 -m forge dashboard forge_assessment_results.json

Output: forge_dashboard.html
"""

import json
import math
import sys
import os
from datetime import datetime

try:
    from forge.trend_visualizer import load_history, generate_trend_section
    from forge.delta_engine import compute_delta
    _TREND_AVAILABLE = True
except ImportError:
    _TREND_AVAILABLE = False

try:
    from forge.platform_segments.databricks_registry import (
        DATABRICKS_SERVICES,
        get_databricks_criterion,
    )
    _DBX_REGISTRY_AVAILABLE = True
except ImportError:
    DATABRICKS_SERVICES = {}
    _DBX_REGISTRY_AVAILABLE = False

    def get_databricks_criterion(pillar: str, index: int):
        return None


def _generate_radar_svg(pillar_names: list, pillar_scores: list) -> str:
    """Generate a 9-sided polygon SVG radar chart for pillar scores (0-100 scale)."""
    n = len(pillar_names)
    cx, cy = 200, 200  # center
    max_r = 150  # maximum radius
    svg_parts = []

    svg_parts.append(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 420" '
        'style="width:100%;height:350px;display:block" preserveAspectRatio="xMidYMid meet">'
    )

    # Helper to get polygon vertex at given radius for index i
    def vertex(i: int, radius: float):
        angle = (2 * math.pi * i / n) - math.pi / 2  # start from top
        x = cx + radius * math.cos(angle)
        y = cy + radius * math.sin(angle)
        return x, y

    # Background grid polygons at 25%, 50%, 75%, 100%
    for level in [0.25, 0.50, 0.75, 1.0]:
        r = max_r * level
        points = " ".join(f"{vertex(i, r)[0]:.1f},{vertex(i, r)[1]:.1f}" for i in range(n))
        svg_parts.append(
            f'  <polygon points="{points}" fill="none" stroke="#30363d" stroke-width="1"/>'
        )

    # Spoke lines from center to each vertex
    for i in range(n):
        x, y = vertex(i, max_r)
        svg_parts.append(
            f'  <line x1="{cx}" y1="{cy}" x2="{x:.1f}" y2="{y:.1f}" stroke="#21262d" stroke-width="1"/>'
        )

    # Data polygon
    data_points = []
    for i, score in enumerate(pillar_scores):
        r = max_r * (score / 100)
        x, y = vertex(i, r)
        data_points.append((x, y))

    points_str = " ".join(f"{x:.1f},{y:.1f}" for x, y in data_points)
    svg_parts.append(
        f'  <polygon points="{points_str}" fill="#388bfd33" stroke="#388bfd" stroke-width="2.5"/>'
    )

    # Data point dots and score values
    for i, (x, y) in enumerate(data_points):
        svg_parts.append(
            f'  <circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="#388bfd" stroke="#0d1117" stroke-width="1.5"/>'
        )

    # Labels for each pillar positioned outside the polygon
    label_r = max_r + 28
    for i in range(n):
        lx, ly = vertex(i, label_r)
        score = pillar_scores[i]
        # Pillar code label
        svg_parts.append(
            f'  <text x="{lx:.1f}" y="{ly:.1f}" text-anchor="middle" '
            f'dominant-baseline="middle" fill="#8b949e" font-size="11" font-weight="600">'
            f'{pillar_names[i]}</text>'
        )
        # Score value below the label
        svg_parts.append(
            f'  <text x="{lx:.1f}" y="{ly + 14:.1f}" text-anchor="middle" '
            f'dominant-baseline="middle" fill="#c9d1d9" font-size="10">'
            f'{score:.0f}%</text>'
        )

    svg_parts.append("</svg>")
    return "\n".join(svg_parts)


def _generate_radar_toggle_section(
    combined_scores: dict[str, float],
    platform_scores: dict[str, dict[str, float]],
    pillar_names: list[str],
) -> str:
    """Generate radar chart section with platform toggle buttons.

    Args:
        combined_scores: Estate-level pillar scores {"P1": 65.0, "P2": 55.0, ...}
        platform_scores: Per-platform pillar scores
                         {"aws": {"P1": 70.0, ...}, "databricks": {"P1": 50.0, ...}}
        pillar_names: List of pillar codes in order ["P1", "P2", ...]

    Returns:
        HTML string with toggle buttons and multiple radar SVGs.
        If only one platform, renders a single radar without toggle controls.
    """
    # If only one platform segment, don't show toggle — just render single radar
    if len(platform_scores) <= 1:
        scores_list = [combined_scores.get(p, 0.0) for p in pillar_names]
        return _generate_radar_svg(pillar_names, scores_list)

    # Build radar SVGs for each view
    combined_list = [combined_scores.get(p, 0.0) for p in pillar_names]
    combined_svg = _generate_radar_svg(pillar_names, combined_list)

    platform_svgs = {}
    for platform, pscores in platform_scores.items():
        plist = [pscores.get(p, 0.0) for p in pillar_names]
        platform_svgs[platform] = _generate_radar_svg(pillar_names, plist)

    # Build toggle buttons
    platform_labels = {
        "aws": "AWS",
        "databricks": "Databricks",
    }

    buttons_html = (
        '<button class="radar-btn active" onclick="showRadar(\'combined\')">Combined</button>'
    )
    for platform in platform_scores:
        label = platform_labels.get(platform, platform.title())
        buttons_html += (
            f'\n    <button class="radar-btn" onclick="showRadar(\'{platform}\')">{label}</button>'
        )

    # Build radar view divs
    views_html = f'  <div id="radar-combined" class="radar-view active">\n    {combined_svg}\n  </div>\n'
    for platform, svg in platform_svgs.items():
        views_html += f'  <div id="radar-{platform}" class="radar-view" style="display:none">\n    {svg}\n  </div>\n'

    # Assemble full section
    section = f'''<div class="radar-section">
  <div class="radar-toggle">
    {buttons_html}
  </div>
{views_html}</div>

<script>
function showRadar(platform) {{
  document.querySelectorAll('.radar-view').forEach(function(el) {{ el.style.display = 'none'; el.classList.remove('active'); }});
  document.querySelectorAll('.radar-btn').forEach(function(el) {{ el.classList.remove('active'); }});
  document.getElementById('radar-' + platform).style.display = 'block';
  document.getElementById('radar-' + platform).classList.add('active');
  event.target.classList.add('active');
}}
</script>'''

    return section


def _generate_gauge_svg(score: float) -> str:
    """Generate an SVG arc gauge showing score 0-100."""
    cx, cy = 150, 120
    r = 90  # radius of the arc center line
    thickness = 28
    svg_parts = []

    svg_parts.append(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 300 170" '
        'style="width:300px;height:170px;display:block" preserveAspectRatio="xMidYMid meet">'
    )

    # Background track
    left_x = cx - r
    right_x = cx + r
    svg_parts.append(
        f'  <path d="M {left_x} {cy} A {r} {r} 0 1 1 {right_x} {cy}" '
        f'fill="none" stroke="#21262d" stroke-width="{thickness}" stroke-linecap="round"/>'
    )

    # Colored fill arc (partial)
    if score > 0:
        sweep_deg = (score / 100) * 180
        end_angle = math.radians(180 - sweep_deg)
        end_x = cx + r * math.cos(end_angle)
        end_y = cy - r * math.sin(end_angle)

        large_arc = 1 if sweep_deg > 180 else 0

        # Band-based color
        if score >= 91:
            fill_color = "#007bff"
        elif score >= 76:
            fill_color = "#28a745"
        elif score >= 51:
            fill_color = "#ffc107"
        elif score >= 26:
            fill_color = "#fd7e14"
        else:
            fill_color = "#dc3545"

        svg_parts.append(
            f'  <path d="M {left_x} {cy} A {r} {r} 0 {large_arc} 1 {end_x:.1f} {end_y:.1f}" '
            f'fill="none" stroke="{fill_color}" stroke-width="{thickness}" stroke-linecap="round"/>'
        )

    # Score text in center
    svg_parts.append(
        f'  <text x="{cx}" y="{cy + 10}" text-anchor="middle" '
        f'dominant-baseline="middle" fill="#c9d1d9" font-size="36" font-weight="800">{score}</text>'
    )
    # Label below
    svg_parts.append(
        f'  <text x="{cx}" y="{cy + 35}" text-anchor="middle" '
        f'fill="#8b949e" font-size="11">FORGE Score</text>'
    )

    # Min/Max labels
    svg_parts.append(
        f'  <text x="{left_x}" y="{cy + 25}" text-anchor="middle" fill="#8b949e" font-size="10">0</text>'
    )
    svg_parts.append(
        f'  <text x="{right_x}" y="{cy + 25}" text-anchor="middle" fill="#8b949e" font-size="10">100</text>'
    )

    svg_parts.append("</svg>")
    return "\n".join(svg_parts)


def generate_dashboard(results_file, output_file="forge_output/forge_dashboard.html"):
    """Generate interactive HTML dashboard from assessment results."""
    os.makedirs(os.path.dirname(output_file) or ".", exist_ok=True)
    with open(results_file) as f:
        data = json.load(f)

    scoring = data["scoring"]
    pillars = data["pillars"]

    # Build pillar data for charts
    pillar_names = [p["code"] for p in pillars]
    pillar_scores_list = [scoring["pillar_scores"][p["code"]]["score_percent"] for p in pillars]

    # Generate SVG charts
    radar_svg = _generate_radar_svg(pillar_names, pillar_scores_list)
    gauge_svg = _generate_gauge_svg(scoring["forge_score"])

    # Band colors
    band_colors = {
        "UNREADY": "#dc3545",
        "FOUNDATIONAL": "#fd7e14",
        "GOVERNED": "#ffc107",
        "AGENT-READY": "#28a745",
        "FORGE-NATIVE": "#007bff"
    }
    band_color = band_colors.get(scoring["band"], "#6c757d")

    # Generate criteria detail HTML
    criteria_html = ""
    for p in pillars:
        criteria_html += f'<div class="pillar-detail" id="detail-{p["code"]}">\n'
        criteria_html += f'  <h3>{p["code"]}: {p["name"]}</h3>\n'
        criteria_html += '  <table class="criteria-table">\n'
        criteria_html += '    <tr><th>#</th><th>Criterion</th>'
        criteria_html += '<th>Status</th><th>Evidence</th><th>Confidence</th></tr>\n'
        for c in p.get("criteria", []):
            status_icon = "✅" if c["met"] else "❌"
            status_class = "met" if c["met"] else "unmet"
            evidence = c.get("evidence", {}).get("description", "N/A")
            confidence = c.get("evidence", {}).get("confidence_percent", 0)
            criteria_html += f'    <tr class="{status_class}">'
            criteria_html += f'<td>{p["code"]}.{c["index"]}</td>'
            criteria_html += f'<td>{c["name"]}</td>'
            criteria_html += f'<td>{status_icon}</td>'
            criteria_html += f'<td class="evidence">{evidence}</td>'
            criteria_html += f'<td><span class="confidence">{confidence}%</span></td>'
            criteria_html += '</tr>\n'
        criteria_html += '  </table>\n</div>\n'

    # Remediation priorities
    remediation_html = ""
    for p in pillars:
        unmet = [c for c in p.get("criteria", []) if not c["met"]]
        if unmet:
            remediation_html += f'<div class="remediation-card">\n'
            remediation_html += f'  <h4>{p["code"]}: {p["name"]} ({len(unmet)} gaps)</h4>\n'
            remediation_html += '  <ul>\n'
            for c in unmet[:5]:
                remediation_html += f'    <li>{p["code"]}.{c["index"]}: {c["name"]}</li>\n'
            if len(unmet) > 5:
                remediation_html += f'    <li><em>...and {len(unmet)-5} more</em></li>\n'
            remediation_html += '  </ul>\n</div>\n'

    # Score-lift recommendations
    recs = []
    for p in pillars:
        code = p["code"]
        weight = {"P1":20,"P2":10,"P3":10,"P4":15,"P5":15,"P6":5,"P7":10,"P8":10,"P9":5}[code]
        unmet_count = sum(1 for c in p.get("criteria",[]) if not c["met"])
        if unmet_count > 0:
            lift_per_criterion = (weight / p["total"]) * scoring["coverage_multiplier"]
            recs.append({
                "pillar": code,
                "name": p["name"],
                "unmet": unmet_count,
                "lift_per": round(lift_per_criterion, 2),
                "total_lift": round(lift_per_criterion * unmet_count, 1)
            })
    recs.sort(key=lambda x: x["lift_per"], reverse=True)

    recs_html = ""
    for r in recs[:7]:
        recs_html += f'<tr><td>{r["pillar"]}</td><td>{r["name"]}</td>'
        recs_html += f'<td>{r["unmet"]}</td><td>+{r["lift_per"]}/criterion</td>'
        recs_html += f'<td><strong>+{r["total_lift"]}</strong></td></tr>\n'

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>FORGE 2.3 Assessment — {data["customer_name"]}</title>
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
.score-hero {{ display: flex; align-items: center; gap: 40px; margin-top: 20px; }}
.score-number {{ font-size: 72px; font-weight: 800; color: {band_color}; }}
.band-badge {{ background: {band_color}; color: #fff; padding: 8px 20px;
              border-radius: 20px; font-weight: 700; font-size: 18px; }}
.score-details {{ color: #8b949e; font-size: 13px; margin-top: 8px; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(400px, 1fr)); gap: 20px; margin-bottom: 24px; }}
.card {{ background: #161b22; border: 1px solid #30363d; border-radius: 12px; padding: 24px; }}
.pillar-bar {{ display: flex; align-items: center; gap: 12px; margin: 8px 0; }}
.pillar-label {{ width: 180px; font-size: 13px; color: #8b949e; }}
.bar-bg {{ flex: 1; height: 24px; background: #21262d; border-radius: 4px; overflow: hidden; }}
.bar-fill {{ height: 100%; border-radius: 4px; transition: width 0.8s ease; }}
.bar-value {{ width: 60px; text-align: right; font-weight: 600; font-size: 13px; }}
</style>
'''

    html += '''<style>
.radar-section { position: relative; }
.radar-toggle { display: flex; gap: 4px; margin-bottom: 12px; }
.radar-btn { padding: 6px 14px; background: #21262d; border: 1px solid #30363d;
             border-radius: 6px; cursor: pointer; font-size: 12px; color: #8b949e; }
.radar-btn.active { background: #388bfd22; border-color: #388bfd; color: #58a6ff; }
.tabs { display: flex; gap: 4px; margin-bottom: 16px; flex-wrap: wrap; }
.tab { padding: 8px 16px; background: #21262d; border: 1px solid #30363d;
       border-radius: 6px; cursor: pointer; font-size: 13px; color: #8b949e; }
.tab.active { background: #388bfd22; border-color: #388bfd; color: #58a6ff; }
.tab-content { display: none; }
.tab-content.active { display: block; }
.criteria-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.criteria-table th { background: #21262d; padding: 10px; text-align: left; color: #8b949e; }
.criteria-table td { padding: 8px 10px; border-bottom: 1px solid #21262d; }
.criteria-table tr.met td { color: #c9d1d9; }
.criteria-table tr.unmet td { color: #f85149; }
.evidence { max-width: 300px; font-size: 12px; color: #8b949e; }
.confidence { background: #21262d; padding: 2px 8px; border-radius: 10px; font-size: 11px; }
.remediation-card { background: #1c1f26; border-left: 3px solid #f0883e;
                    padding: 16px; margin: 8px 0; border-radius: 0 8px 8px 0; }
.remediation-card h4 { color: #f0883e; margin-bottom: 8px; font-size: 14px; }
.remediation-card li { margin-left: 20px; font-size: 13px; color: #8b949e; }
table.recs { width: 100%; border-collapse: collapse; font-size: 13px; }
table.recs th { background: #21262d; padding: 10px; text-align: left; }
table.recs td { padding: 8px 10px; border-bottom: 1px solid #21262d; }
.stack-section { margin: 16px 0; padding: 12px; background: #1c2128; border-radius: 8px; }
.stack-title { font-weight: 700; color: #58a6ff; margin-bottom: 8px; }
@media (max-width: 768px) {
  .grid { grid-template-columns: 1fr; }
  .score-hero { flex-direction: column; gap: 16px; }
}
</style>
'''

    # Build profile display string
    profile_data = data.get("profile") or data.get("metadata", {}).get("profile", {})
    if profile_data:
        profile_display = " | ".join(
            f"{k.replace('_', ' ').title()}: <strong>{v}</strong>"
            for k, v in profile_data.items()
        )
    else:
        profile_display = "<em>No profile declared</em>"

    html += f'''</head>
<body>
<div class="container">
  <header>
    <h1>🔥 FORGE 2.3 Assessment Dashboard</h1>
    <p class="meta">
      Customer: <strong>{data["customer_name"]}</strong> |
      Account: <strong>{data["account_id"]}</strong> |
      Region: <strong>{data["region"]}</strong> |
      Date: <strong>{data["timestamp"][:10]}</strong>
    </p>
    <p class="meta" style="margin-top:4px">
      Profile: {profile_display}
    </p>
    <div class="score-hero">
      <div>
        <div class="score-number">{scoring["forge_score"]}</div>
        <span class="band-badge">{scoring["band"]}</span>
      </div>
      <div>{gauge_svg}</div>
      <div class="score-details">
        <p>Raw Score: {scoring["raw_score"]} | Coverage Multiplier: {scoring["coverage_multiplier"]} | Penalty: {scoring["penalty_percent"]}%</p>
        <p>Assessment ID: {data["assessment_id"]}</p>
      </div>
    </div>
  </header>

  <div class="grid">
    <div class="card">
      <h2>Pillar Scores</h2>
'''

    # Pillar bars with color coding
    colors_by_score = lambda s: "#dc3545" if s < 25 else "#fd7e14" if s < 50 else "#ffc107" if s < 75 else "#28a745"
    for p in pillars:
        code = p["code"]
        pct = scoring["pillar_scores"][code]["score_percent"]
        met = scoring["pillar_scores"][code]["met"]
        total = scoring["pillar_scores"][code]["total"]
        color = colors_by_score(pct)
        html += f'''      <div class="pillar-bar">
        <span class="pillar-label">{code}: {p["name"][:25]}</span>
        <div class="bar-bg"><div class="bar-fill" style="width:{pct}%;background:{color}"></div></div>
        <span class="bar-value" style="color:{color}">{pct:.0f}% ({met}/{total})</span>
      </div>\n'''

    html += f'''    </div>
    <div class="card">
      <h2>Score Radar</h2>
      {radar_svg}
    </div>
  </div>

  <div class="grid">
    <div class="card">
      <h2>Stack Readiness</h2>
'''

    # Stack groupings
    stacks = [
        ("Stack 1 — Data Plane Foundation", ["P1","P2","P3"], 40),
        ("Stack 2 — Governance & Trust", ["P4","P5","P6","P7"], 45),
        ("Stack 3 — Agentic Orchestration", ["P8","P9"], 15)
    ]
    for sname, codes, weight in stacks:
        avg = sum(scoring["pillar_scores"][c]["score_percent"] for c in codes) / len(codes)
        scolor = colors_by_score(avg)
        html += f'''      <div class="stack-section">
        <div class="stack-title">{sname} (Weight: {weight}%)</div>
        <div class="bar-bg"><div class="bar-fill" style="width:{avg:.0f}%;background:{scolor}"></div></div>
        <span style="color:{scolor};font-weight:600">{avg:.1f}%</span>
      </div>\n'''

    html += f'''    </div>
    <div class="card">
      <h2>Score-Lift Recommendations</h2>
      <p style="color:#8b949e;font-size:13px;margin-bottom:12px">Sorted by impact per criterion remediated</p>
      <table class="recs">
        <tr><th>Pillar</th><th>Name</th><th>Gaps</th><th>Lift/Fix</th><th>Max Lift</th></tr>
        {recs_html}
      </table>
    </div>
  </div>

'''

    # Embed trend visualization section
    if _TREND_AVAILABLE:
        try:
            trend_data = load_history()
            delta_result = compute_delta()
            trend_html_fragment = generate_trend_section(trend_data, delta_result)
            html += f'''  {trend_html_fragment}

'''
        except Exception:
            pass  # Trend section simply won't appear if something goes wrong

    html += '''  <div class="card">
    <h2>Criteria Detail</h2>
    <div class="tabs">
'''
    for p in pillars:
        code = p["code"]
        html += f'      <div class="tab" onclick="showPillar(\'{code}\')" id="tab-{code}">{code}</div>\n'

    html += f'''    </div>
    <div id="criteria-panels">
      {criteria_html}
    </div>
  </div>

  <div class="card" style="margin-top:20px">
    <h2>Remediation Roadmap</h2>
    <p style="color:#8b949e;font-size:13px;margin-bottom:16px">
      Top gaps per pillar — address in stack order (Stack 1 → Stack 2 → Stack 3)
    </p>
    {remediation_html}
  </div>

  <div class="card" style="margin-top:20px">
    <h2>Band Advancement Path</h2>
    <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:12px">
'''

    bands_list = [
        ("UNREADY", "0-25", "#dc3545"),
        ("FOUNDATIONAL", "26-50", "#fd7e14"),
        ("GOVERNED", "51-75", "#ffc107"),
        ("AGENT-READY", "76-90", "#28a745"),
        ("FORGE-NATIVE", "91-100", "#007bff")
    ]
    for bname, brange, bclr in bands_list:
        active = "border-width:3px" if bname == scoring["band"] else "opacity:0.5"
        html += f'''      <div style="background:{bclr}22;border:2px solid {bclr};{active};
                          border-radius:8px;padding:12px 20px;text-align:center;min-width:120px">
        <div style="font-weight:700;color:{bclr}">{bname}</div>
        <div style="font-size:12px;color:#8b949e">{brange}</div>
      </div>\n'''

    html += '''    </div>
  </div>
</div>

<script>
// Tab switching
function showPillar(code) {
  document.querySelectorAll('.pillar-detail').forEach(el => el.style.display = 'none');
  document.querySelectorAll('.tab').forEach(el => el.classList.remove('active'));
  document.getElementById('detail-' + code).style.display = 'block';
  document.getElementById('tab-' + code).classList.add('active');
}
// Show P1 by default
showPillar('P1');
</script>
</body>
</html>'''

    with open(output_file, "w") as f:
        f.write(html)

    print(f"✓ Dashboard generated: {output_file}")
    print(f"  Open in browser: file://{os.path.abspath(output_file)}")



# ─── Multi-Platform Estate Dashboard ──────────────────────────────────────────

# Band color lookup shared between functions
_BAND_COLORS = {
    "UNREADY": "#dc3545",
    "FOUNDATIONAL": "#fd7e14",
    "GOVERNED": "#ffc107",
    "AGENT-READY": "#28a745",
    "FORGE-NATIVE": "#007bff",
}


def _generate_platform_badges(segments: list) -> str:
    """Create HTML badges for each platform's score and band.

    Args:
        segments: List of platform segment dicts, each containing
                  'platform', 'forge_score', and 'score_band'.

    Returns:
        HTML string with platform badge elements.
    """
    badges_html = '<div class="platform-badges">\n'
    for seg in segments:
        platform = seg["platform"]
        score = seg["forge_score"]
        band = seg["score_band"]
        band_color = _BAND_COLORS.get(band, "#6c757d")
        css_class = platform.lower().replace(" ", "-")
        badges_html += (
            f'  <div class="platform-badge {css_class}">\n'
            f'    <span class="platform-name">{platform.upper()}</span>\n'
            f'    <span class="platform-score">{score}</span>\n'
            f'    <span class="platform-band" style="background:{band_color}">{band}</span>\n'
            f'  </div>\n'
        )
    badges_html += '</div>'
    return badges_html


def _platform_tag_css() -> str:
    """Return CSS styles for inline platform tags in criteria tables."""
    return '''
.platform-tag { padding: 2px 6px; border-radius: 4px; font-size: 10px; font-weight: 600; display: inline-block; margin: 1px 2px; }
.platform-tag.aws { background: #ff990022; color: #ff9900; border: 1px solid #ff990044; }
.platform-tag.dbx { background: #ff383822; color: #ff3838; border: 1px solid #ff383844; }
.platform-tag.estate { background: #388bfd22; color: #58a6ff; border: 1px solid #388bfd44; }
'''


def _generate_estate_criteria_html(merged_criteria: list, segments: list) -> str:
    """Generate criteria detail HTML for estate dashboard with platform badges.

    Each criterion row includes:
      - Platform column: badges showing which platform(s) the criterion applies to
      - For binary criteria that failed: evidence shows which platform(s) failed
      - For analog criteria: evidence shows per-platform breakdown

    Args:
        merged_criteria: List of merged criterion dicts from estate assessment.
        segments: Platform segment dicts to look up per-platform details.

    Returns:
        HTML string for the criteria detail section.
    """
    # Build per-platform criterion lookup: {(pillar, index): [criterion_results]}
    platform_criterion_lookup: dict[tuple[str, int], list[dict]] = {}
    for seg in segments:
        platform = seg.get("platform", "")
        for c in seg.get("criteria", []):
            key = (c.get("pillar", ""), c.get("index", 0))
            if key not in platform_criterion_lookup:
                platform_criterion_lookup[key] = []
            platform_criterion_lookup[key].append({**c, "platform": platform})

    # Group merged criteria by pillar
    criteria_by_pillar: dict[str, list[dict]] = {}
    for c in merged_criteria:
        pillar = c.get("pillar", "")
        if pillar not in criteria_by_pillar:
            criteria_by_pillar[pillar] = []
        criteria_by_pillar[pillar].append(c)

    # Platform label mapping
    platform_labels = {
        "aws": "AWS",
        "databricks": "DBX",
    }
    platform_css = {
        "aws": "aws",
        "databricks": "dbx",
    }

    html = ""
    pillar_codes = sorted(criteria_by_pillar.keys())
    for code in pillar_codes:
        criteria_list = criteria_by_pillar[code]
        # Determine pillar name from first criterion
        pillar_name = ""
        if criteria_list:
            pillar_name = criteria_list[0].get("pillar_name", code)

        html += f'<div class="pillar-detail" id="detail-{code}">\n'
        html += f'  <h3>{code}: {pillar_name}</h3>\n'
        html += '  <table class="criteria-table">\n'
        html += '    <tr><th>#</th><th>Criterion</th><th>Platform</th>'
        html += '<th>Status</th><th class="evidence">Evidence</th><th>Confidence</th></tr>\n'

        for c in criteria_list:
            index = c.get("index", "")
            name = c.get("name", "")
            score = c.get("score", 0.0)
            met = score >= 0.5
            status_icon = "✅" if met else "❌"
            status_class = "met" if met else "unmet"
            confidence = round(c.get("confidence_score", 0.0) * 100)
            criterion_type = c.get("criterion_type", "BINARY")

            # Determine which platforms this criterion applies to
            key = (code, index)
            per_platform_results = platform_criterion_lookup.get(key, [])
            relevant_platforms = [
                r["platform"] for r in per_platform_results
                if r.get("relevance_status", "") != "NOT_APPLICABLE"
            ]

            # Generate platform badges
            if len(relevant_platforms) == 0:
                # Fallback: use the merged criterion's platform field
                crit_platform = c.get("platform", "estate")
                if crit_platform == "estate":
                    badges = '<span class="platform-tag estate">Estate</span>'
                else:
                    label = platform_labels.get(crit_platform, crit_platform.upper())
                    css_cls = platform_css.get(crit_platform, "estate")
                    badges = f'<span class="platform-tag {css_cls}">{label}</span>'
            elif len(relevant_platforms) == 1:
                plat = relevant_platforms[0]
                label = platform_labels.get(plat, plat.upper())
                css_cls = platform_css.get(plat, "estate")
                badges = f'<span class="platform-tag {css_cls}">{label}</span>'
            else:
                badges = " ".join(
                    f'<span class="platform-tag {platform_css.get(p, "estate")}">'
                    f'{platform_labels.get(p, p.upper())}</span>'
                    for p in sorted(relevant_platforms)
                )

            # Build evidence based on criterion type
            if criterion_type == "ANALOG" or criterion_type == "analog":
                # Show per-platform breakdown for analog criteria
                evidence = _build_analog_evidence(c, per_platform_results, platform_labels)
            elif not met and (criterion_type == "BINARY" or criterion_type == "binary"):
                # Show which platform(s) failed for binary criteria
                evidence = _build_binary_failure_evidence(c, per_platform_results, platform_labels)
            else:
                # Default: use the merged evidence field
                evidence = c.get("evidence", "N/A")

            html += f'    <tr class="{status_class}">'
            html += f'<td>{code}.{index}</td>'
            html += f'<td>{name}</td>'
            html += f'<td>{badges}</td>'
            html += f'<td>{status_icon}</td>'
            html += f'<td class="evidence">{evidence}</td>'
            html += f'<td><span class="confidence">{confidence}%</span></td>'
            html += '</tr>\n'

        html += '  </table>\n</div>\n'

    return html


def _build_analog_evidence(
    merged_criterion: dict,
    per_platform_results: list[dict],
    platform_labels: dict[str, str],
) -> str:
    """Build evidence string for analog criterion showing per-platform breakdown.

    Format: "Combined: 66.7% — AWS: 80/100, DBX: 20/50"

    Args:
        merged_criterion: The estate-level merged criterion dict.
        per_platform_results: Per-platform criterion results for this criterion.
        platform_labels: Platform name → display label mapping.

    Returns:
        Formatted evidence string with per-platform breakdown.
    """
    # Get the combined score
    score = merged_criterion.get("score", 0.0)
    combined_pct = f"{score * 100:.1f}%"

    # Build per-platform parts
    parts = []
    relevant_results = [
        r for r in per_platform_results
        if r.get("relevance_status", "") != "NOT_APPLICABLE"
    ]

    for r in relevant_results:
        platform = r.get("platform", "")
        label = platform_labels.get(platform, platform.upper())
        analog_detail = r.get("analog_detail")
        if analog_detail:
            num = analog_detail.get("numerator", 0)
            den = analog_detail.get("denominator", 0)
            parts.append(f"{label}: {num}/{den}")
        else:
            # Fallback: show the score as percentage
            plat_score = r.get("score", 0.0)
            parts.append(f"{label}: {plat_score * 100:.0f}%")

    if parts:
        breakdown = ", ".join(parts)
        return f"Combined: {combined_pct} — {breakdown}"
    else:
        # No per-platform data available, use merged evidence
        return merged_criterion.get("evidence", f"Score: {combined_pct}")


def _build_binary_failure_evidence(
    merged_criterion: dict,
    per_platform_results: list[dict],
    platform_labels: dict[str, str],
) -> str:
    """Build evidence string for binary criterion that failed, showing which platforms failed.

    Format: "Failed on: databricks" or "Failed on: aws, databricks"

    Args:
        merged_criterion: The estate-level merged criterion dict.
        per_platform_results: Per-platform criterion results for this criterion.
        platform_labels: Platform name → display label mapping.

    Returns:
        Formatted evidence string indicating which platform(s) failed.
    """
    failed_platforms = []
    relevant_results = [
        r for r in per_platform_results
        if r.get("relevance_status", "") != "NOT_APPLICABLE"
    ]

    for r in relevant_results:
        if r.get("score", 0.0) < 0.5:
            platform = r.get("platform", "")
            failed_platforms.append(platform)

    if failed_platforms:
        failed_names = ", ".join(sorted(failed_platforms))
        return f"Failed on: {failed_names}"
    else:
        # Should not normally reach here since the criterion is unmet
        return merged_criterion.get("evidence", "Failed")


def _get_databricks_service_label(pillar: str, index: int) -> str:
    """Look up the primary Databricks service display name for a criterion.

    Args:
        pillar: Pillar code (e.g., "P4").
        index: Criterion index within pillar (1-based).

    Returns:
        Display name of the first service (e.g., "Delta Live Tables"),
        or empty string if not found.
    """
    criterion_def = get_databricks_criterion(pillar, index)
    if criterion_def and criterion_def.services:
        service_key = criterion_def.services[0]
        return DATABRICKS_SERVICES.get(service_key, service_key)
    return ""


def _generate_estate_remediation_html(merged_criteria: list, segments: list) -> str:
    """Generate remediation roadmap HTML grouped by platform.

    Walks each platform segment's criteria, finds unmet ones (score < 0.5
    and relevance_status == "relevant"), groups them by platform → pillar,
    and renders platform-specific remediation cards.

    For Databricks criteria, each item references the relevant Databricks service
    (e.g., "Delta Live Tables", "Unity Catalog"). For AWS criteria, the criterion
    name is shown directly.

    Args:
        merged_criteria: List of merged criterion result dicts (estate-level).
        segments: Platform segment dicts, each with 'platform' and 'criteria' keys.

    Returns:
        HTML string with platform-grouped remediation cards.
    """
    # Collect unmet criteria per platform grouped by pillar
    # Structure: { platform: { pillar: [criterion_dict, ...] } }
    platform_gaps: dict[str, dict[str, list]] = {}

    for seg in segments:
        platform = seg.get("platform", "unknown")
        criteria = seg.get("criteria", [])

        for c in criteria:
            relevance = c.get("relevance_status", "")
            # Normalize relevance check — handle enum string representation
            is_relevant = relevance in (
                "relevant", "RELEVANT",
                "RelevanceStatus.RELEVANT",
            )
            score = c.get("score", 0.0)

            if is_relevant and score < 0.5:
                pillar = c.get("pillar", "")
                if platform not in platform_gaps:
                    platform_gaps[platform] = {}
                if pillar not in platform_gaps[platform]:
                    platform_gaps[platform][pillar] = []
                platform_gaps[platform][pillar].append(c)

    if not platform_gaps:
        return ""

    # Platform display config
    platform_config = {
        "aws": {
            "label": "AWS Remediation",
            "icon": "☁️",
            "header_class": "aws-header",
            "card_class": "platform-aws",
        },
        "databricks": {
            "label": "Databricks Remediation",
            "icon": "🧱",
            "header_class": "dbx-header",
            "card_class": "platform-dbx",
        },
    }

    # Pillar display names
    pillar_names = {
        "P1": "Agent Access & Discovery",
        "P2": "Semantic Richness",
        "P3": "Data Lineage & Provenance",
        "P4": "Data Quality",
        "P5": "Access Control & Identity",
        "P6": "Observability & Audit",
        "P7": "Real-Time Freshness",
        "P8": "Orchestration Maturity",
        "P9": "Feedback & Adaptation",
    }

    html = '<div class="remediation-section">\n'

    # Render in a consistent platform order
    platform_order = ["aws", "databricks"]
    for platform in platform_order:
        if platform not in platform_gaps:
            continue

        config = platform_config.get(platform, {
            "label": f"{platform.title()} Remediation",
            "icon": "🔧",
            "header_class": "",
            "card_class": "",
        })

        html += (
            f'  <h3 class="platform-header {config["header_class"]}">\n'
            f'    <span class="platform-icon">{config["icon"]}</span> {config["label"]}\n'
            f'  </h3>\n'
        )

        # Sort pillars by code
        sorted_pillars = sorted(platform_gaps[platform].keys())

        for pillar in sorted_pillars:
            gaps = platform_gaps[platform][pillar]
            pillar_display = pillar_names.get(pillar, pillar)
            gap_count = len(gaps)

            html += f'  <div class="remediation-card {config["card_class"]}">\n'
            html += f'    <h4>{pillar}: {pillar_display} ({gap_count} gaps)</h4>\n'
            html += '    <ul>\n'

            for c in gaps[:5]:
                index = c.get("index", "")
                name = c.get("name", "")

                # Build the service reference
                if platform == "databricks":
                    service_label = _get_databricks_service_label(pillar, index)
                    if service_label:
                        html += f'      <li>{pillar}.{index}: {name} — {service_label}</li>\n'
                    else:
                        html += f'      <li>{pillar}.{index}: {name}</li>\n'
                else:
                    # AWS: just show criterion name
                    html += f'      <li>{pillar}.{index}: {name}</li>\n'

            if gap_count > 5:
                html += f'      <li><em>...and {gap_count - 5} more</em></li>\n'

            html += '    </ul>\n'
            html += '  </div>\n'

    # Handle any platforms not in our predefined order
    for platform in sorted(platform_gaps.keys()):
        if platform in platform_order:
            continue
        config = {
            "label": f"{platform.title()} Remediation",
            "icon": "🔧",
            "header_class": "",
            "card_class": "",
        }
        html += (
            f'  <h3 class="platform-header">\n'
            f'    <span class="platform-icon">{config["icon"]}</span> {config["label"]}\n'
            f'  </h3>\n'
        )
        sorted_pillars = sorted(platform_gaps[platform].keys())
        for pillar in sorted_pillars:
            gaps = platform_gaps[platform][pillar]
            pillar_display = pillar_names.get(pillar, pillar)
            gap_count = len(gaps)
            html += f'  <div class="remediation-card">\n'
            html += f'    <h4>{pillar}: {pillar_display} ({gap_count} gaps)</h4>\n'
            html += '    <ul>\n'
            for c in gaps[:5]:
                index = c.get("index", "")
                name = c.get("name", "")
                html += f'      <li>{pillar}.{index}: {name}</li>\n'
            if gap_count > 5:
                html += f'      <li><em>...and {gap_count - 5} more</em></li>\n'
            html += '    </ul>\n'
            html += '  </div>\n'

    html += '</div>'
    return html


def _estate_remediation_css() -> str:
    """Return CSS styles for platform-grouped remediation cards."""
    return '''
.remediation-section { margin-top: 8px; }
.platform-header { margin-top: 16px; margin-bottom: 8px; font-size: 16px; }
.platform-header .platform-icon { margin-right: 4px; }
.aws-header { color: #ff9900; }
.dbx-header { color: #ff3838; }
.remediation-card.platform-aws { border-left-color: #ff9900; }
.remediation-card.platform-dbx { border-left-color: #ff3838; }
'''


def _platform_badges_css() -> str:
    """Return CSS styles for platform badges."""
    return '''
.platform-badges {
  display: flex;
  gap: 16px;
  margin-top: 16px;
  flex-wrap: wrap;
}
.platform-badge {
  display: flex;
  align-items: center;
  gap: 10px;
  background: #161b22;
  border: 1px solid #30363d;
  border-radius: 8px;
  padding: 10px 18px;
}
.platform-badge .platform-name {
  font-weight: 700;
  font-size: 13px;
  color: #8b949e;
  letter-spacing: 0.5px;
}
.platform-badge .platform-score {
  font-weight: 800;
  font-size: 20px;
  color: #c9d1d9;
}
.platform-badge .platform-band {
  color: #fff;
  padding: 3px 10px;
  border-radius: 12px;
  font-weight: 600;
  font-size: 11px;
  text-transform: uppercase;
}
'''


def generate_estate_dashboard(
    estate_result_file: str,
    output_file: str = "forge_output/forge_dashboard.html",
) -> None:
    """Generate HTML dashboard from a multi-platform estate assessment.

    If the input contains multiple platform segments, shows:
      - Estate Score as primary gauge
      - Per-platform scores as secondary badges below

    If single segment, renders identically to the standard dashboard
    (no platform badges, same layout as before).

    Args:
        estate_result_file: Path to estate assessment JSON.
        output_file: Output HTML file path.
    """
    os.makedirs(os.path.dirname(output_file) or ".", exist_ok=True)
    with open(estate_result_file) as f:
        data = json.load(f)

    segments = data.get("segments", [])
    is_multi_platform = len(segments) > 1

    # Determine the primary score and band
    if is_multi_platform:
        estate = data.get("estate", {})
        primary_score = estate.get("forge_score", 0.0)
        primary_band = estate.get("score_band", "UNREADY")
    else:
        # Single segment — use that platform's score directly
        if segments:
            primary_score = segments[0].get("forge_score", 0.0)
            primary_band = segments[0].get("score_band", "UNREADY")
        else:
            # Fallback: try top-level scoring (legacy format)
            scoring = data.get("scoring", {})
            primary_score = scoring.get("forge_score", 0.0)
            primary_band = scoring.get("band", "UNREADY")

    band_color = _BAND_COLORS.get(primary_band, "#6c757d")

    # Build pillar data from merged_pillars or segments
    merged_pillars = data.get("merged_pillars", [])
    if not merged_pillars and segments:
        # Fallback to first segment's pillars
        merged_pillars = segments[0].get("pillars", [])

    pillar_names = [p.get("code", f"P{i+1}") for i, p in enumerate(merged_pillars)]
    pillar_scores_list = [p.get("raw_score", 0.0) for p in merged_pillars]

    # Generate SVG charts
    radar_svg = _generate_radar_svg(pillar_names, pillar_scores_list)
    gauge_svg = _generate_gauge_svg(primary_score)

    # Platform badges (only for multi-platform)
    platform_badges_html = ""
    if is_multi_platform:
        platform_badges_html = _generate_platform_badges(segments)

    # Metadata
    metadata = data.get("metadata", {})
    customer_name = metadata.get("customer_name", "Unknown")
    timestamp = metadata.get("timestamp", "")
    platforms_assessed = metadata.get("platforms_assessed", [s.get("platform", "") for s in segments])

    # Build criteria detail from merged_criteria using platform-aware function
    merged_criteria = data.get("merged_criteria", [])
    criteria_by_pillar: dict = {}
    for c in merged_criteria:
        pillar = c.get("pillar", "")
        if pillar not in criteria_by_pillar:
            criteria_by_pillar[pillar] = []
        criteria_by_pillar[pillar].append(c)

    # Use the new platform-aware criteria HTML generator for multi-platform
    if is_multi_platform:
        criteria_html = _generate_estate_criteria_html(merged_criteria, segments)
    else:
        criteria_html = ""
        for p in merged_pillars:
            code = p.get("code", "")
            name = p.get("name", "")
            criteria_html += f'<div class="pillar-detail" id="detail-{code}">\n'
            criteria_html += f'  <h3>{code}: {name}</h3>\n'
            criteria_html += '  <table class="criteria-table">\n'
            criteria_html += '    <tr><th>#</th><th>Criterion</th>'
            criteria_html += '<th>Status</th><th>Evidence</th><th>Confidence</th></tr>\n'
            for c in criteria_by_pillar.get(code, []):
                score = c.get("score", 0.0)
                met = score >= 0.5
                status_icon = "✅" if met else "❌"
                status_class = "met" if met else "unmet"
                evidence = c.get("evidence", "N/A")
                confidence = round(c.get("confidence_score", 0.0) * 100)
                criteria_html += f'    <tr class="{status_class}">'
                criteria_html += f'<td>{code}.{c.get("index", "")}</td>'
                criteria_html += f'<td>{c.get("name", "")}</td>'
                criteria_html += f'<td>{status_icon}</td>'
                criteria_html += f'<td class="evidence">{evidence}</td>'
                criteria_html += f'<td><span class="confidence">{confidence}%</span></td>'
                criteria_html += '</tr>\n'
            criteria_html += '  </table>\n</div>\n'

    # Remediation priorities — platform-grouped for multi-platform, standard for single
    if is_multi_platform:
        remediation_html = _generate_estate_remediation_html(merged_criteria, segments)
    else:
        remediation_html = ""
        for p in merged_pillars:
            code = p.get("code", "")
            name = p.get("name", "")
            unmet = [c for c in criteria_by_pillar.get(code, []) if c.get("score", 0.0) < 0.5]
            if unmet:
                remediation_html += f'<div class="remediation-card">\n'
                remediation_html += f'  <h4>{code}: {name} ({len(unmet)} gaps)</h4>\n'
                remediation_html += '  <ul>\n'
                for c in unmet[:5]:
                    remediation_html += f'    <li>{code}.{c.get("index","")}: {c.get("name","")}</li>\n'
                if len(unmet) > 5:
                    remediation_html += f'    <li><em>...and {len(unmet)-5} more</em></li>\n'
                remediation_html += '  </ul>\n</div>\n'

    # Profile display
    profile_data = metadata.get("profile", {})
    if profile_data:
        profile_display = " | ".join(
            f"{k.replace('_', ' ').title()}: <strong>{v}</strong>"
            for k, v in profile_data.items()
        )
    else:
        profile_display = "<em>No profile declared</em>"

    # Platforms display
    platforms_display = ", ".join(p.upper() for p in platforms_assessed) if platforms_assessed else "N/A"

    # Build the HTML
    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>FORGE 2.3 {"Estate " if is_multi_platform else ""}Assessment — {customer_name}</title>
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
.score-hero {{ display: flex; align-items: center; gap: 40px; margin-top: 20px; }}
.score-number {{ font-size: 72px; font-weight: 800; color: {band_color}; }}
.band-badge {{ background: {band_color}; color: #fff; padding: 8px 20px;
              border-radius: 20px; font-weight: 700; font-size: 18px; }}
.score-details {{ color: #8b949e; font-size: 13px; margin-top: 8px; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(400px, 1fr)); gap: 20px; margin-bottom: 24px; }}
.card {{ background: #161b22; border: 1px solid #30363d; border-radius: 12px; padding: 24px; }}
.pillar-bar {{ display: flex; align-items: center; gap: 12px; margin: 8px 0; }}
.pillar-label {{ width: 180px; font-size: 13px; color: #8b949e; }}
.bar-bg {{ flex: 1; height: 24px; background: #21262d; border-radius: 4px; overflow: hidden; }}
.bar-fill {{ height: 100%; border-radius: 4px; transition: width 0.8s ease; }}
.bar-value {{ width: 60px; text-align: right; font-weight: 600; font-size: 13px; }}
{_platform_badges_css() if is_multi_platform else ""}
{_platform_tag_css() if is_multi_platform else ""}
{_estate_remediation_css() if is_multi_platform else ""}
</style>
'''

    html += '''<style>
.tabs { display: flex; gap: 4px; margin-bottom: 16px; flex-wrap: wrap; }
.tab { padding: 8px 16px; background: #21262d; border: 1px solid #30363d;
       border-radius: 6px; cursor: pointer; font-size: 13px; color: #8b949e; }
.tab.active { background: #388bfd22; border-color: #388bfd; color: #58a6ff; }
.tab-content { display: none; }
.tab-content.active { display: block; }
.criteria-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.criteria-table th { background: #21262d; padding: 10px; text-align: left; color: #8b949e; }
.criteria-table td { padding: 8px 10px; border-bottom: 1px solid #21262d; }
.criteria-table tr.met td { color: #c9d1d9; }
.criteria-table tr.unmet td { color: #f85149; }
.evidence { max-width: 300px; font-size: 12px; color: #8b949e; }
.confidence { background: #21262d; padding: 2px 8px; border-radius: 10px; font-size: 11px; }
.remediation-card { background: #1c1f26; border-left: 3px solid #f0883e;
                    padding: 16px; margin: 8px 0; border-radius: 0 8px 8px 0; }
.remediation-card h4 { color: #f0883e; margin-bottom: 8px; font-size: 14px; }
.remediation-card li { margin-left: 20px; font-size: 13px; color: #8b949e; }
table.recs { width: 100%; border-collapse: collapse; font-size: 13px; }
table.recs th { background: #21262d; padding: 10px; text-align: left; }
table.recs td { padding: 8px 10px; border-bottom: 1px solid #21262d; }
@media (max-width: 768px) {
  .grid { grid-template-columns: 1fr; }
  .score-hero { flex-direction: column; gap: 16px; }
}
</style>
'''

    # Score details
    if is_multi_platform:
        estate = data.get("estate", {})
        raw_score = estate.get("raw_score", 0.0)
        coverage_mult = estate.get("coverage_multiplier", 1.0)
        score_label = "Estate Score"
    else:
        if segments:
            seg_summary = segments[0]
            raw_score = seg_summary.get("raw_score", 0.0)
            coverage_mult = seg_summary.get("coverage_multiplier", 1.0)
        else:
            raw_score = 0.0
            coverage_mult = 1.0
        score_label = "FORGE Score"

    html += f'''</head>
<body>
<div class="container">
  <header>
    <h1>🔥 FORGE 2.3 {"Estate " if is_multi_platform else ""}Assessment Dashboard</h1>
    <p class="meta">
      Customer: <strong>{customer_name}</strong> |
      Platforms: <strong>{platforms_display}</strong> |
      Date: <strong>{timestamp[:10] if timestamp else "N/A"}</strong>
    </p>
    <p class="meta" style="margin-top:4px">
      Profile: {profile_display}
    </p>
    <div class="score-hero">
      <div>
        <div class="score-number">{primary_score}</div>
        <span class="band-badge">{primary_band}</span>
      </div>
      <div>{gauge_svg}</div>
      <div class="score-details">
        <p>{score_label}: {primary_score} | Raw: {raw_score} | Coverage Multiplier: {coverage_mult}</p>
      </div>
    </div>
    {platform_badges_html}
  </header>

  <div class="grid">
    <div class="card">
      <h2>Pillar Scores</h2>
'''

    # Pillar bars
    colors_by_score = lambda s: "#dc3545" if s < 25 else "#fd7e14" if s < 50 else "#ffc107" if s < 75 else "#28a745"
    for p in merged_pillars:
        code = p.get("code", "")
        name = p.get("name", "")
        pct = p.get("raw_score", 0.0)
        relevant = p.get("relevant_count", 0)
        na_count = p.get("not_applicable_count", 0)
        total = relevant + na_count
        color = colors_by_score(pct)
        html += f'''      <div class="pillar-bar">
        <span class="pillar-label">{code}: {name[:25]}</span>
        <div class="bar-bg"><div class="bar-fill" style="width:{pct}%;background:{color}"></div></div>
        <span class="bar-value" style="color:{color}">{pct:.0f}%</span>
      </div>\n'''

    html += f'''    </div>
    <div class="card">
      <h2>Score Radar</h2>
      {radar_svg}
    </div>
  </div>

'''

    html += f'''  <div class="card">
    <h2>Criteria Detail</h2>
    <div class="tabs">
'''
    for p in merged_pillars:
        code = p.get("code", "")
        html += f'      <div class="tab" onclick="showPillar(\'{code}\')" id="tab-{code}">{code}</div>\n'

    html += f'''    </div>
    <div id="criteria-panels">
      {criteria_html}
    </div>
  </div>

  <div class="card" style="margin-top:20px">
    <h2>Remediation Roadmap</h2>
    <p style="color:#8b949e;font-size:13px;margin-bottom:16px">
      {"Platform-grouped remediation — each gap points to the relevant platform service" if is_multi_platform else "Top gaps per pillar — address in stack order (Stack 1 &rarr; Stack 2 &rarr; Stack 3)"}
    </p>
    {remediation_html}
  </div>

  <div class="card" style="margin-top:20px">
    <h2>Band Advancement Path</h2>
    <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:12px">
'''

    bands_list = [
        ("UNREADY", "0-25", "#dc3545"),
        ("FOUNDATIONAL", "26-50", "#fd7e14"),
        ("GOVERNED", "51-75", "#ffc107"),
        ("AGENT-READY", "76-90", "#28a745"),
        ("FORGE-NATIVE", "91-100", "#007bff")
    ]
    for bname, brange, bclr in bands_list:
        active = "border-width:3px" if bname == primary_band else "opacity:0.5"
        html += f'''      <div style="background:{bclr}22;border:2px solid {bclr};{active};
                          border-radius:8px;padding:12px 20px;text-align:center;min-width:120px">
        <div style="font-weight:700;color:{bclr}">{bname}</div>
        <div style="font-size:12px;color:#8b949e">{brange}</div>
      </div>\n'''

    html += '''    </div>
  </div>
</div>

<script>
// Tab switching
function showPillar(code) {
  document.querySelectorAll('.pillar-detail').forEach(el => el.style.display = 'none');
  document.querySelectorAll('.tab').forEach(el => el.classList.remove('active'));
  document.getElementById('detail-' + code).style.display = 'block';
  document.getElementById('tab-' + code).classList.add('active');
}
// Show first pillar by default
var firstTab = document.querySelector('.tab');
if (firstTab) firstTab.click();
</script>
</body>
</html>'''

    with open(output_file, "w") as f:
        f.write(html)

    print(f"✓ Estate dashboard generated: {output_file}")
    print(f"  Open in browser: file://{os.path.abspath(output_file)}")

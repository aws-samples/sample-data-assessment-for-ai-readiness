"""Pure SVG trend chart generator for the FORGE Score trend visualization.

Generates an HTML <div> with an inline SVG line chart that plots
FORGE Score over time, including band boundary lines and color-coded
last segment indicating trend direction. Works fully offline with
zero external dependencies.
"""

import logging
from pathlib import Path
from typing import Optional

from forge.delta_engine import DeltaResult
from forge.delta_engine.reader import read_history
from forge.trend_visualizer import TrendChartData, TrendDataPoint

logger = logging.getLogger(__name__)


def load_history(
    history_path: Path = Path("forge_output/forge_history.jsonl"),
    max_points: int = 50,
) -> TrendChartData:
    """Load history data for trend visualization.

    Reads forge_history.jsonl, extracts timestamp, forge_score, and score_band
    for each record, caps at the most recent max_points entries, and determines
    the trend direction.

    Args:
        history_path: Path to the JSONL history file.
        max_points: Maximum number of data points to include (default 50).

    Returns:
        TrendChartData with available=False if fewer than 2 records exist.
    """
    records = read_history(history_path)

    # Cap to most recent max_points
    if len(records) > max_points:
        records = records[-max_points:]

    if len(records) < 2:
        return TrendChartData(
            data_points=[
                TrendDataPoint(
                    timestamp=r.get("timestamp", ""),
                    forge_score=r.get("forge_score", 0.0),
                    score_band=r.get("score_band", "UNREADY"),
                )
                for r in records
            ],
            available=False,
        )

    data_points = [
        TrendDataPoint(
            timestamp=r.get("timestamp", ""),
            forge_score=r.get("forge_score", 0.0),
            score_band=r.get("score_band", "UNREADY"),
        )
        for r in records
    ]

    # Determine trend direction from last two points
    last_score = data_points[-1].forge_score
    prev_score = data_points[-2].forge_score
    if last_score > prev_score:
        trend_direction = "improving"
    elif last_score < prev_score:
        trend_direction = "declining"
    else:
        trend_direction = "stable"

    return TrendChartData(
        data_points=data_points,
        trend_direction=trend_direction,
        available=True,
    )


def generate_trend_section(
    trend_data: TrendChartData,
    delta_result: Optional[DeltaResult] = None,
) -> str:
    """Generate HTML fragment with inline SVG trend chart for embedding in the dashboard.

    Produces a <div> containing:
    - Delta summary header (score change, improved/regressed counts)
    - Pure SVG line chart plotting FORGE Score (0-100) against assessment dates
    - Dashed horizontal band boundary lines at 25, 50, 75, 90
    - Color-coded last segment (green=improving, red=declining/stable)
    - Data point circles with score value labels
    - "Last assessed: <timestamp>" footer

    If trend_data.available is False, returns a placeholder message div.

    Args:
        trend_data: The prepared trend chart data.
        delta_result: Optional delta result for the summary header.

    Returns:
        HTML string fragment ready for dashboard embedding.
    """
    if not trend_data.available:
        return (
            '<div class="card" style="margin-top:20px">\n'
            '  <h2>Score Trend</h2>\n'
            '  <p style="color:#8b949e;padding:24px;text-align:center">'
            "Insufficient data for trend visualization. "
            "At least 2 assessment records are required.</p>\n"
            "</div>"
        )

    # Build delta summary header
    delta_header = _build_delta_header(delta_result)

    # Build SVG chart
    svg_chart = _build_svg_trend_chart(trend_data)

    # Footer with last assessed timestamp
    last_timestamp = trend_data.data_points[-1].timestamp
    footer = f'<p style="color:#8b949e;font-size:12px;margin-top:12px;text-align:right">Last assessed: {last_timestamp}</p>'

    html = f'''<div class="card" style="margin-top:20px">
  <h2>Score Trend</h2>
  {delta_header}
  <div style="width:100%;margin-top:16px">
    {svg_chart}
  </div>
  {footer}
</div>'''

    return html


def _build_svg_trend_chart(trend_data: TrendChartData) -> str:
    """Generate a pure inline SVG line chart for the trend data."""
    # Chart dimensions (viewBox-based for responsiveness)
    vb_width = 800
    vb_height = 250
    margin_left = 60
    margin_right = 30
    margin_top = 20
    margin_bottom = 50

    plot_width = vb_width - margin_left - margin_right
    plot_height = vb_height - margin_top - margin_bottom

    scores = [dp.forge_score for dp in trend_data.data_points]
    labels = [_format_timestamp_label(dp.timestamp) for dp in trend_data.data_points]
    n = len(scores)

    # Map data to plot coordinates
    def x_pos(i: int) -> float:
        if n == 1:
            return margin_left + plot_width / 2
        return margin_left + (i / (n - 1)) * plot_width

    def y_pos(score: float) -> float:
        # y=0 is top in SVG, score 100 should be at top
        return margin_top + (1 - score / 100) * plot_height

    # Colors
    main_color = "#388bfd"
    last_segment_color = (
        "#28a745" if trend_data.trend_direction == "improving" else "#dc3545"
    )

    # Band boundary info
    band_boundaries = trend_data.band_boundaries  # [25, 50, 75, 90]
    band_labels_map = {
        25: "UNREADY→FOUND.",
        50: "FOUND.→GOVERNED",
        75: "GOVERNED→AGENT-READY",
        90: "AGENT-READY→NATIVE",
    }
    band_colors = {
        25: "#dc3545",
        50: "#fd7e14",
        75: "#ffc107",
        90: "#28a745",
    }

    svg_parts = []
    svg_parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {vb_width} {vb_height}" '
        f'style="width:100%;height:250px;display:block" preserveAspectRatio="xMidYMid meet">'
    )

    # Y-axis grid lines (at 0, 25, 50, 75, 100)
    for val in [0, 25, 50, 75, 100]:
        y = y_pos(val)
        svg_parts.append(
            f'  <line x1="{margin_left}" y1="{y:.1f}" x2="{vb_width - margin_right}" y2="{y:.1f}" '
            f'stroke="#21262d" stroke-width="1"/>'
        )
        # Y-axis label
        svg_parts.append(
            f'  <text x="{margin_left - 8}" y="{y:.1f}" text-anchor="end" '
            f'dominant-baseline="middle" fill="#8b949e" font-size="11">{val}</text>'
        )

    # Band boundary dashed lines with labels
    for b in band_boundaries:
        y = y_pos(b)
        color = band_colors.get(b, "#8b949e")
        label = band_labels_map.get(b, "")
        svg_parts.append(
            f'  <line x1="{margin_left}" y1="{y:.1f}" x2="{vb_width - margin_right}" y2="{y:.1f}" '
            f'stroke="{color}" stroke-width="1" stroke-dasharray="6,4" opacity="0.7"/>'
        )
        svg_parts.append(
            f'  <text x="{vb_width - margin_right - 4}" y="{y - 5:.1f}" text-anchor="end" '
            f'fill="#8b949e" font-size="9">{label}</text>'
        )

    # X-axis labels (dates)
    for i, label in enumerate(labels):
        x = x_pos(i)
        svg_parts.append(
            f'  <text x="{x:.1f}" y="{vb_height - 5}" text-anchor="middle" '
            f'fill="#8b949e" font-size="10" transform="rotate(-30 {x:.1f} {vb_height - 5})">{label}</text>'
        )

    # Line segments — main color for all except last segment
    for i in range(n - 1):
        x1, y1 = x_pos(i), y_pos(scores[i])
        x2, y2 = x_pos(i + 1), y_pos(scores[i + 1])
        # Last segment uses trend color
        color = last_segment_color if i == n - 2 else main_color
        svg_parts.append(
            f'  <line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
            f'stroke="{color}" stroke-width="3" stroke-linecap="round"/>'
        )

    # Data point circles and score labels
    for i, score in enumerate(scores):
        x, y = x_pos(i), y_pos(score)
        # Circle color: last point uses trend color, others use main
        if i == n - 1:
            pt_color = last_segment_color
        elif i == n - 2 and n > 2:
            pt_color = main_color
        else:
            pt_color = main_color
        svg_parts.append(
            f'  <circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="{pt_color}" stroke="#0d1117" stroke-width="2"/>'
        )
        # Score value label above the point
        svg_parts.append(
            f'  <text x="{x:.1f}" y="{y - 12:.1f}" text-anchor="middle" '
            f'fill="#c9d1d9" font-size="11" font-weight="600">{score}</text>'
        )

    # Y-axis title
    svg_parts.append(
        f'  <text x="14" y="{vb_height / 2}" text-anchor="middle" '
        f'fill="#8b949e" font-size="11" transform="rotate(-90 14 {vb_height / 2})">FORGE Score</text>'
    )

    svg_parts.append("</svg>")
    return "\n".join(svg_parts)


def _build_delta_header(delta_result: Optional[DeltaResult]) -> str:
    """Build the delta summary header HTML."""
    if delta_result is None or not delta_result.available:
        return ""

    delta = delta_result.score_delta
    if delta > 0:
        arrow = "▲"
        color = "#28a745"
        sign = "+"
    elif delta < 0:
        arrow = "▼"
        color = "#dc3545"
        sign = ""
    else:
        arrow = "■"
        color = "#8b949e"
        sign = ""

    improved = delta_result.improved_count
    regressed = delta_result.regressed_count

    parts = []
    if improved > 0:
        parts.append(f'<span style="color:#28a745">{improved} improved</span>')
    if regressed > 0:
        parts.append(f'<span style="color:#dc3545">{regressed} regressed</span>')

    pillar_summary = " | ".join(parts) if parts else ""

    header = (
        f'<div style="display:flex;align-items:center;gap:16px;margin-top:8px">'
        f'<span style="font-size:24px;font-weight:700;color:{color}">'
        f"{arrow} {sign}{delta} pts</span>"
        f'<span style="font-size:14px;color:#8b949e">{pillar_summary}</span>'
        f"</div>"
    )

    return header


def _format_timestamp_label(timestamp: str) -> str:
    """Format an ISO 8601 timestamp into a short date label for the x-axis."""
    # Handle both full ISO and date-only formats
    if "T" in timestamp:
        return timestamp.split("T")[0]
    return timestamp[:10] if len(timestamp) >= 10 else timestamp

"""DAFM Trend Visualizer — generates trend chart data and HTML section for the dashboard.

Public API:
    - TrendDataPoint: Single assessment data point for the trend chart
    - TrendChartData: Complete trend chart dataset with metadata
    - load_history: Load and prepare history data for trend visualization
    - generate_trend_section: Generate HTML fragment for embedding in the dashboard
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from dafm.delta_engine import DeltaResult


@dataclass
class TrendDataPoint:
    """A single data point on the trend chart."""

    timestamp: str  # ISO 8601
    dafm_score: float
    score_band: str


@dataclass
class TrendChartData:
    """Complete dataset for the trend visualization."""

    data_points: list[TrendDataPoint]
    band_boundaries: list[int] = field(default_factory=lambda: [25, 50, 75, 90])
    trend_direction: str = "stable"  # "improving" | "declining" | "stable"
    available: bool = False  # False if < 2 records exist


def load_history(
    history_path: Path = Path("dafm_output/dafm_history.jsonl"),
    max_points: int = 50,
) -> TrendChartData:
    """Load history data for trend visualization.

    Reads dafm_history.jsonl via the delta engine reader, extracts
    timestamp, DAFM Score, and Score Band for each record, and returns
    at most max_points most recent assessments.

    Args:
        history_path: Path to the JSONL history file.
        max_points: Maximum number of data points to include (default 50).

    Returns:
        TrendChartData with available=False if fewer than 2 records exist.
    """
    from dafm.trend_visualizer.chart import load_history as _load_history

    return _load_history(history_path, max_points)


def generate_trend_section(
    trend_data: TrendChartData,
    delta_result: Optional[DeltaResult] = None,
) -> str:
    """Generate HTML fragment for embedding in the dashboard.

    Produces a <div> containing:
    - Delta summary header (score change, improved/regressed counts)
    - Highcharts line chart config for time-series DAFM Score
    - Score_Band boundary lines at 25, 50, 75, 90
    - Color-coded last segment (green=improving, red=declining)
    - "Last assessed: <timestamp>" footer

    If trend_data.available is False, returns a placeholder message.

    Args:
        trend_data: The prepared trend chart data.
        delta_result: Optional delta result for the summary header.

    Returns:
        HTML string fragment ready for dashboard embedding.
    """
    from dafm.trend_visualizer.chart import generate_trend_section as _generate

    return _generate(trend_data, delta_result)


__all__ = [
    "TrendDataPoint",
    "TrendChartData",
    "load_history",
    "generate_trend_section",
]

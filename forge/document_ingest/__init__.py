"""Document ingestion module for Databricks assessment.

Provides parsers for Databricks cost usage exports and configuration documents,
extracting criterion evidence to pre-fill the assessment before follow-up questions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

__all__ = [
    "CostSignal",
    "DocumentEvidence",
    "parse_cost_usage",
    "parse_config_export",
]


@dataclass
class CostSignal:
    """Extracted cost/usage signal from a Databricks billing export."""

    service: str  # "sql_warehouse", "jobs_compute", etc.
    spend_30d: float  # 30-day spend in USD
    active: bool  # Non-zero spend = active
    compute_hours: Optional[float] = None


@dataclass
class DocumentEvidence:
    """Evidence extracted from an uploaded document."""

    criterion_id: str  # "P4.2"
    score: Optional[float]  # If determinable from doc
    evidence: str  # What was found
    confidence: float  # Extraction reliability (0.6–0.85)
    source_file: str  # Filename


def parse_cost_usage(file_path: str) -> list[CostSignal]:
    """Parse a Databricks cost usage export (CSV or PDF).

    Identifies which services are active and at what scale.

    Args:
        file_path: Path to the cost usage file (CSV or PDF format).

    Returns:
        List of CostSignal objects, one per identified service.

    Raises:
        FileNotFoundError: If file_path does not exist.
    """
    from forge.document_ingest.cost_parser import parse_cost_usage as _parse

    return _parse(file_path)


# Config parser — implemented in config_parser.py (task 6.3)
from forge.document_ingest.config_parser import parse_config_export as parse_config_export  # noqa: E501, F401

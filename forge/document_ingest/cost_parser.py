"""
FORGE 2.3 Assessment Workbench — Databricks Cost Usage Parser

Parses Databricks cost usage exports (CSV or PDF) to identify which services
are active and at what spend level. This is the highest-priority document in
the document-first assessment flow — it determines service existence and scale.

Supported formats:
    - CSV: Databricks billing export with service/category, spend, and usage columns
    - PDF: Basic text extraction to detect service names and spend summaries

Usage:
    from forge.document_ingest.cost_parser import parse_cost_usage

    signals = parse_cost_usage("path/to/cost_usage.csv")
    for signal in signals:
        print(f"{signal.service}: ${signal.spend_30d:.2f} (active={signal.active})")
"""
from __future__ import annotations

import csv
import logging
import os
import re
from typing import Optional

from forge.document_ingest import CostSignal

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Resource-exhaustion guards (Guardian finding C2 / threat T5)
# Untrusted documents are parsed locally; cap size and row/field counts to
# prevent a malicious or malformed file from exhausting memory/CPU.
# ---------------------------------------------------------------------------

MAX_FILE_SIZE_BYTES = 100 * 1024 * 1024  # 100 MB hard cap before parsing
MAX_CSV_ROWS = 1_000_000                 # bound the number of data rows read
MAX_FIELD_SIZE_BYTES = 1 * 1024 * 1024   # 1 MB per-field cap (csv.field_size_limit)


class DocumentTooLargeError(ValueError):
    """Raised when an input document exceeds the configured size/row limits."""


def _check_file_size(file_path: str) -> None:
    """Reject files larger than MAX_FILE_SIZE_BYTES before any parsing begins."""
    size = os.path.getsize(file_path)
    if size > MAX_FILE_SIZE_BYTES:
        raise DocumentTooLargeError(
            f"Input file {file_path} is {size} bytes, exceeding the "
            f"{MAX_FILE_SIZE_BYTES}-byte limit. Refusing to parse."
        )


# ---------------------------------------------------------------------------
# Billing category → DATABRICKS_SERVICES key mapping
# ---------------------------------------------------------------------------

BILLING_CATEGORY_MAP: dict[str, str] = {
    # SQL Warehouse variants
    "sql": "sql_warehouse",
    "sql warehouse": "sql_warehouse",
    "sql warehouses": "sql_warehouse",
    "serverless sql": "sql_warehouse",
    "serverless sql warehouse": "sql_warehouse",
    # Workflows / Jobs / Compute
    "jobs": "databricks_workflows",
    "jobs compute": "databricks_workflows",
    "jobs light": "databricks_workflows",
    "all-purpose compute": "databricks_workflows",
    "all purpose compute": "databricks_workflows",
    "interactive": "databricks_workflows",
    "interactive compute": "databricks_workflows",
    "automated": "databricks_workflows",
    "workflows": "databricks_workflows",
    # Delta Live Tables
    "dlt": "delta_live_tables",
    "delta live tables": "delta_live_tables",
    "dlt pipelines": "delta_live_tables",
    "pipelines": "delta_live_tables",
    # MLflow
    "mlflow": "mlflow",
    "mlflow experiments": "mlflow",
    "experiments": "mlflow",
    # Model Serving
    "model serving": "model_serving",
    "serving": "model_serving",
    "inference": "model_serving",
    "serverless real-time inference": "model_serving",
    "foundation model": "model_serving",
    # Unity Catalog
    "unity catalog": "unity_catalog",
    "uc": "unity_catalog",
    # Storage / Delta Lake
    "storage": "delta_lake",
    "dbfs": "delta_lake",
    "delta": "delta_lake",
    "managed storage": "delta_lake",
    # Streaming
    "streaming": "structured_streaming",
    "structured streaming": "structured_streaming",
    # System Tables / Audit
    "system tables": "system_tables",
    "audit logs": "system_tables",
    "audit": "system_tables",
}


# Column name patterns for auto-detection
_SERVICE_COL_PATTERNS = re.compile(
    r"(?:service|category|sku|product|billing.?category|usage.?type|sku.?name)",
    re.IGNORECASE,
)
_SPEND_COL_PATTERNS = re.compile(
    r"(?:spend|cost|amount|charge|total|price|usd|dollars)",
    re.IGNORECASE,
)
_COMPUTE_COL_PATTERNS = re.compile(
    r"(?:dbu|compute.?hours|dbus|usage|hours|quantity|units)",
    re.IGNORECASE,
)


def parse_cost_usage(file_path: str) -> list[CostSignal]:
    """Parse a Databricks cost usage export (CSV or PDF).

    Identifies which services are active and at what scale. This is the
    highest-priority document — it determines service existence.

    Args:
        file_path: Path to the cost usage file (CSV or PDF format).

    Returns:
        List of CostSignal objects, one per identified service.

    Raises:
        FileNotFoundError: If file_path does not exist.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Cost usage file not found: {file_path}")

    _check_file_size(file_path)

    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".csv":
        return _parse_csv(file_path)
    elif ext == ".pdf":
        return _parse_pdf(file_path)
    else:
        logger.warning(
            "Unsupported file format '%s' for cost usage parsing. "
            "Expected .csv or .pdf. Returning empty list.",
            ext,
        )
        return []


# ---------------------------------------------------------------------------
# CSV Parsing
# ---------------------------------------------------------------------------


def _parse_csv(file_path: str) -> list[CostSignal]:
    """Parse a Databricks cost usage CSV export.

    Strategy:
        1. Read header row and identify service, spend, and compute columns
        2. Iterate rows, mapping each billing category to a service key
        3. Aggregate spend and compute hours per service
        4. Return one CostSignal per service with active=spend>0
    """
    with open(file_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        try:
            headers = next(reader)
        except StopIteration:
            logger.warning("CSV file is empty: %s", file_path)
            return []

    # Identify column indices
    service_col = _find_column(headers, _SERVICE_COL_PATTERNS)
    spend_col = _find_column(headers, _SPEND_COL_PATTERNS)
    compute_col = _find_column(headers, _COMPUTE_COL_PATTERNS)

    if service_col is None:
        logger.warning(
            "No recognizable service/category column found in CSV headers: %s. "
            "Returning empty list.",
            headers,
        )
        return []

    # Aggregate per service
    service_totals: dict[str, dict[str, float]] = {}  # service_key → {spend, compute}

    with open(file_path, newline="", encoding="utf-8-sig") as f:
        # Bound per-field size to prevent a single multi-MB field from
        # exhausting memory (Guardian C2 / threat T5).
        csv.field_size_limit(MAX_FIELD_SIZE_BYTES)
        reader = csv.reader(f)
        next(reader)  # skip header
        for row_num, row in enumerate(reader, start=2):
            if row_num - 1 > MAX_CSV_ROWS:
                logger.warning(
                    "CSV %s exceeded %d data rows; truncating parse at the limit.",
                    file_path,
                    MAX_CSV_ROWS,
                )
                break
            if not row or len(row) <= service_col:
                continue

            raw_category = row[service_col].strip()
            service_key = _map_category_to_service(raw_category)
            if service_key is None:
                logger.debug(
                    "Row %d: unrecognized billing category '%s', skipping.",
                    row_num,
                    raw_category,
                )
                continue

            spend = _parse_numeric(row, spend_col)
            compute = _parse_numeric(row, compute_col)

            if service_key not in service_totals:
                service_totals[service_key] = {"spend": 0.0, "compute": 0.0}

            # Missing or non-numeric spend/compute parses to None; treat as 0.0
            # so malformed rows don't crash aggregation (WI-2 / Guardian C2).
            if spend is not None:
                service_totals[service_key]["spend"] += spend
            if compute is not None:
                service_totals[service_key]["compute"] += compute

    # Build CostSignal list
    signals: list[CostSignal] = []
    for svc_key, totals in sorted(service_totals.items()):
        spend = totals["spend"]
        compute = totals["compute"] if totals["compute"] > 0 else None
        signals.append(
            CostSignal(
                service=svc_key,
                spend_30d=round(spend, 2),
                active=spend > 0,
                compute_hours=round(compute, 2) if compute else None,
            )
        )

    return signals


def _find_column(headers: list[str], pattern: re.Pattern) -> Optional[int]:
    """Find the first column index matching a regex pattern."""
    for idx, header in enumerate(headers):
        if pattern.search(header.strip()):
            return idx
    return None


def _map_category_to_service(raw_category: str) -> Optional[str]:
    """Map a raw billing category string to a canonical service key.

    Uses case-insensitive matching against BILLING_CATEGORY_MAP.
    """
    normalized = raw_category.lower().strip()

    # Direct match
    if normalized in BILLING_CATEGORY_MAP:
        return BILLING_CATEGORY_MAP[normalized]

    # Substring match — check if any known key appears in the raw category
    for key, service in BILLING_CATEGORY_MAP.items():
        if key in normalized:
            return service

    return None


def _parse_numeric(row: list[str], col_idx: Optional[int]) -> Optional[float]:
    """Safely extract a numeric value from a CSV row at given column index."""
    if col_idx is None or col_idx >= len(row):
        return None
    raw = row[col_idx].strip()
    # Remove currency symbols and commas
    cleaned = raw.replace("$", "").replace(",", "").replace(" ", "")
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# PDF Parsing
# ---------------------------------------------------------------------------


def _parse_pdf(file_path: str) -> list[CostSignal]:
    """Parse a Databricks cost usage PDF for service indicators.

    Uses basic text extraction. If PDF libraries are unavailable,
    returns an empty list with a warning.

    PDF parsing is more limited than CSV — primarily detects which services
    appear in the document and marks them as active. Spend amounts are
    extracted where recognizable patterns are found.
    """
    text = _extract_pdf_text(file_path)
    if text is None:
        return []

    return _detect_services_from_text(text)


def _extract_pdf_text(file_path: str) -> Optional[str]:
    """Attempt to extract text from a PDF using available libraries.

    Tries PyPDF2 first, then pdfplumber. Returns None if neither is available.
    """
    # Try pypdf (maintained successor to the deprecated/EOL PyPDF2 — see threat model T5/WI-2)
    try:
        import pypdf  # noqa: F401

        text_parts: list[str] = []
        with open(file_path, "rb") as f:
            reader = pypdf.PdfReader(f)
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
        if text_parts:
            return "\n".join(text_parts)
    except ImportError:
        pass
    except Exception as e:
        logger.warning("pypdf failed to parse %s: %s", file_path, e)

    # Try pdfplumber
    try:
        import pdfplumber  # noqa: F401

        text_parts = []
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
        if text_parts:
            return "\n".join(text_parts)
    except ImportError:
        pass
    except Exception as e:
        logger.warning("pdfplumber failed to parse %s: %s", file_path, e)

    logger.warning(
        "No PDF parsing library available (install PyPDF2 or pdfplumber). "
        "Cannot extract text from: %s",
        file_path,
    )
    return None


def _detect_services_from_text(text: str) -> list[CostSignal]:
    """Detect Databricks services mentioned in extracted PDF text.

    Scans for known billing keywords and spend patterns. More limited
    than CSV parsing — primarily identifies service presence.
    """
    text_lower = text.lower()
    detected_services: dict[str, float] = {}

    # Check for each billing category in the text
    for category, service_key in BILLING_CATEGORY_MAP.items():
        if category in text_lower:
            if service_key not in detected_services:
                detected_services[service_key] = 0.0

    # Try to extract spend amounts near service mentions
    # Pattern: "$X,XXX.XX" or "X,XXX.XX USD"
    spend_pattern = re.compile(
        r"\$\s*([\d,]+\.?\d*)|"
        r"([\d,]+\.?\d*)\s*(?:USD|usd|dollars)",
    )

    for service_key in list(detected_services.keys()):
        # Look for spend amounts near service name mentions
        _find_spend_for_service(text, text_lower, service_key, detected_services, spend_pattern)

    # Build CostSignal list
    signals: list[CostSignal] = []
    for svc_key in sorted(detected_services.keys()):
        spend = detected_services[svc_key]
        signals.append(
            CostSignal(
                service=svc_key,
                spend_30d=round(spend, 2),
                active=True,  # Presence in cost doc implies active
                compute_hours=None,
            )
        )

    return signals


def _find_spend_for_service(
    text: str,
    text_lower: str,
    service_key: str,
    detected_services: dict[str, float],
    spend_pattern: re.Pattern,
) -> None:
    """Try to find a spend amount near a service mention in the text.

    Searches for dollar amounts within a window of the service name.
    Updates detected_services in place if a spend amount is found.
    """
    # Find service-related keywords in the text
    service_keywords = [
        k for k, v in BILLING_CATEGORY_MAP.items() if v == service_key
    ]

    for keyword in service_keywords:
        idx = text_lower.find(keyword)
        if idx == -1:
            continue

        # Look for spend in a window around the keyword (200 chars after)
        window = text[idx : idx + 200]
        matches = spend_pattern.findall(window)
        for match in matches:
            amount_str = match[0] if match[0] else match[1]
            if amount_str:
                try:
                    amount = float(amount_str.replace(",", ""))
                    if amount > detected_services[service_key]:
                        detected_services[service_key] = amount
                    return  # Use first found amount
                except ValueError:
                    continue

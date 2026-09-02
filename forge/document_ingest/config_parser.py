"""
FORGE 2.3 Assessment Workbench — Document Config Parser

Parses UC config exports, workspace descriptions, and architecture documents
to extract criterion-relevant evidence for Databricks assessment pre-fill.

Supports: .txt, .json, .yaml/.yml (direct text), .pdf (best-effort extraction).

Usage:
    from forge.document_ingest.config_parser import parse_config_export

    evidence = parse_config_export("architecture_overview.txt")
"""
from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any

from forge.document_ingest import DocumentEvidence

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Evidence pattern definitions — maps keyword patterns to criteria
# ---------------------------------------------------------------------------

EVIDENCE_PATTERNS: list[dict[str, Any]] = [
    # P1: Agent Access & Discovery
    {
        "criterion_id": "P1.1",
        "patterns": [r"unity catalog", r"uc api", r"catalog api", r"rest api.*catalog"],
        "score": 1.0,
        "confidence": 0.70,
        "evidence_template": "Document mentions Unity Catalog API usage: {match}",
    },
    {
        "criterion_id": "P1.3",
        "patterns": [r"schema introspection", r"column.*metadata", r"information_schema"],
        "score": 1.0,
        "confidence": 0.70,
        "evidence_template": "Document references schema introspection: {match}",
    },
    {
        "criterion_id": "P1.5",
        "patterns": [r"three.level namespace", r"catalog\.schema\.table", r"three-level"],
        "score": 1.0,
        "confidence": 0.75,
        "evidence_template": "Document references three-level namespace: {match}",
    },
    {
        "criterion_id": "P1.6",
        "patterns": [r"delta lake", r"delta format", r"open.?format"],
        "score": 1.0,
        "confidence": 0.65,
        "evidence_template": "Document mentions Delta Lake format: {match}",
    },
    {
        "criterion_id": "P1.8",
        "patterns": [r"cross.workspace", r"shared metastore", r"metastore.*shared"],
        "score": 1.0,
        "confidence": 0.70,
        "evidence_template": "Document references cross-workspace discovery: {match}",
    },
    {
        "criterion_id": "P1.9",
        "patterns": [r"sql warehouse", r"serverless.*warehouse", r"sql endpoint"],
        "score": 1.0,
        "confidence": 0.70,
        "evidence_template": "Document mentions SQL Warehouse access: {match}",
    },
    {
        "criterion_id": "P1.10",
        "patterns": [r"time.?travel", r"version.*history", r"delta.*history"],
        "score": 1.0,
        "confidence": 0.65,
        "evidence_template": "Document references Delta time-travel: {match}",
    },
    # P3: Data Lineage & Provenance
    {
        "criterion_id": "P3.1",
        "patterns": [r"lineage.*enabled", r"lineage tracking", r"uc lineage"],
        "score": 1.0,
        "confidence": 0.75,
        "evidence_template": "Document references lineage configuration: {match}",
    },
    {
        "criterion_id": "P3.2",
        "patterns": [r"column.level lineage", r"column lineage", r"fine.grained lineage"],
        "score": 1.0,
        "confidence": 0.70,
        "evidence_template": "Document mentions column-level lineage: {match}",
    },
    {
        "criterion_id": "P3.4",
        "patterns": [r"lineage.*api", r"lineage.*rest", r"programmatic.*lineage"],
        "score": 1.0,
        "confidence": 0.70,
        "evidence_template": "Document references lineage API access: {match}",
    },
    {
        "criterion_id": "P3.5",
        "patterns": [r"dlt.*lineage", r"delta live.*lineage", r"pipeline lineage"],
        "score": 1.0,
        "confidence": 0.70,
        "evidence_template": "Document mentions DLT pipeline lineage: {match}",
    },
    # P4: Data Quality, Contracts & Classification
    {
        "criterion_id": "P4.1",
        "patterns": [r"dlt expectations", r"data quality.*rules", r"delta live.*expectations"],
        "score": 1.0,
        "confidence": 0.70,
        "evidence_template": "Document mentions DQ rules: {match}",
    },
    {
        "criterion_id": "P4.4",
        "patterns": [r"quality.*metrics.*stored", r"expectation.*results.*table", r"dq.*history"],
        "score": 1.0,
        "confidence": 0.65,
        "evidence_template": "Document references stored quality metrics: {match}",
    },
    {
        "criterion_id": "P4.5",
        "patterns": [r"schema enforcement", r"enforce schema", r"schema validation"],
        "score": 1.0,
        "confidence": 0.75,
        "evidence_template": "Document mentions schema enforcement: {match}",
    },
    {
        "criterion_id": "P4.6",
        "patterns": [r"schema evolution", r"merge schema", r"schema.*change"],
        "score": 1.0,
        "confidence": 0.70,
        "evidence_template": "Document references schema evolution: {match}",
    },
    {
        "criterion_id": "P4.7",
        "patterns": [r"pii.*tag", r"classification.*tag", r"sensitive.*column.*tag"],
        "score": 1.0,
        "confidence": 0.65,
        "evidence_template": "Document mentions PII tagging: {match}",
    },
    {
        "criterion_id": "P4.9",
        "patterns": [r"table constraint", r"not null.*constraint", r"primary key.*delta"],
        "score": 1.0,
        "confidence": 0.65,
        "evidence_template": "Document references table constraints: {match}",
    },
    # P5: Access Control, Identity & Tenancy
    {
        "criterion_id": "P5.1",
        "patterns": [r"column.*mask", r"dynamic masking", r"data masking"],
        "score": 1.0,
        "confidence": 0.70,
        "evidence_template": "Document references column masking: {match}",
    },
    {
        "criterion_id": "P5.2",
        "patterns": [r"row filter", r"row.*security", r"row.level"],
        "score": 1.0,
        "confidence": 0.70,
        "evidence_template": "Document references row filtering: {match}",
    },
    {
        "criterion_id": "P5.3",
        "patterns": [r"grant.*revoke", r"uc permissions", r"unity catalog.*permission"],
        "score": 1.0,
        "confidence": 0.70,
        "evidence_template": "Document mentions UC permissions model: {match}",
    },
    {
        "criterion_id": "P5.4",
        "patterns": [r"service principal", r"machine.*identity", r"spn.*access"],
        "score": 1.0,
        "confidence": 0.70,
        "evidence_template": "Document references service principal identity: {match}",
    },
    {
        "criterion_id": "P5.6",
        "patterns": [r"token.*management", r"token.*polic", r"pat.*restrict"],
        "score": 1.0,
        "confidence": 0.65,
        "evidence_template": "Document mentions token management: {match}",
    },
    # P6: Observability & Audit
    {
        "criterion_id": "P6.1",
        "patterns": [r"system tables", r"audit log", r"audit.*enabled"],
        "score": 1.0,
        "confidence": 0.75,
        "evidence_template": "Document mentions audit capability: {match}",
    },
    {
        "criterion_id": "P6.2",
        "patterns": [r"data access.*log", r"access.*audit", r"read.*write.*log"],
        "score": 1.0,
        "confidence": 0.70,
        "evidence_template": "Document references data access logging: {match}",
    },
    {
        "criterion_id": "P6.4",
        "patterns": [r"cost.*attribution", r"billing.*table", r"spend.*per.*workspace"],
        "score": 1.0,
        "confidence": 0.65,
        "evidence_template": "Document mentions cost attribution: {match}",
    },
    {
        "criterion_id": "P6.5",
        "patterns": [r"pipeline.*observ", r"dlt.*monitor", r"pipeline.*metrics"],
        "score": 1.0,
        "confidence": 0.65,
        "evidence_template": "Document references pipeline observability: {match}",
    },
    {
        "criterion_id": "P6.6",
        "patterns": [r"mlflow.*experiment", r"experiment.*tracking", r"mlflow.*log"],
        "score": 1.0,
        "confidence": 0.70,
        "evidence_template": "Document mentions MLflow experiment tracking: {match}",
    },
    # P7: Real-Time, Freshness & Zero-ETL
    {
        "criterion_id": "P7.1",
        "patterns": [r"streaming table", r"real.?time pipeline", r"structured streaming"],
        "score": 1.0,
        "confidence": 0.70,
        "evidence_template": "Document references streaming: {match}",
    },
    {
        "criterion_id": "P7.4",
        "patterns": [r"change data feed", r"change data capture", r"cdf.*enabled"],
        "score": 1.0,
        "confidence": 0.70,
        "evidence_template": "Document mentions Change Data Feed: {match}",
    },
    {
        "criterion_id": "P7.5",
        "patterns": [r"incremental.*process", r"incremental.*load", r"micro.?batch"],
        "score": 1.0,
        "confidence": 0.65,
        "evidence_template": "Document references incremental processing: {match}",
    },
    {
        "criterion_id": "P7.9",
        "patterns": [r"auto.?loader", r"cloud.?files", r"file.*ingestion.*auto"],
        "score": 1.0,
        "confidence": 0.70,
        "evidence_template": "Document mentions Auto Loader: {match}",
    },
]


# ---------------------------------------------------------------------------
# Supported file extensions
# ---------------------------------------------------------------------------

_TEXT_EXTENSIONS = {".txt", ".json", ".yaml", ".yml", ".md", ".csv", ".conf", ".cfg"}
_PDF_EXTENSION = ".pdf"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _read_text_file(file_path: str) -> str:
    """Read a text file and return its content."""
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def _read_pdf_file(file_path: str) -> str:
    """Attempt to read text from a PDF file.

    Uses pypdf (maintained successor to the deprecated/EOL PyPDF2). Returns an
    empty string on graceful failure (library missing or unreadable PDF).
    """
    try:
        import pypdf  # noqa: F401

        reader = pypdf.PdfReader(file_path)
        pages_text = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                pages_text.append(text)
        return "\n".join(pages_text)
    except ImportError:
        pass
    except Exception as e:
        logger.warning("pypdf failed to parse %s: %s", file_path, e)

    # No PDF library available — graceful failure
    return ""


def _extract_content(file_path: str) -> str:
    """Extract text content from a file based on its extension.

    Args:
        file_path: Path to the file to read.

    Returns:
        Text content of the file, or empty string if unreadable.
    """
    ext = Path(file_path).suffix.lower()

    if ext in _TEXT_EXTENSIONS:
        return _read_text_file(file_path)
    elif ext == _PDF_EXTENSION:
        return _read_pdf_file(file_path)
    else:
        # Attempt to read as text; return empty on failure (binary/unreadable)
        try:
            return _read_text_file(file_path)
        except (UnicodeDecodeError, ValueError):
            return ""


def _scan_for_evidence(
    content: str, source_file: str
) -> list[DocumentEvidence]:
    """Scan text content against all evidence patterns.

    Args:
        content: The text content to scan.
        source_file: Filename for evidence attribution.

    Returns:
        List of DocumentEvidence objects for all matches found.
    """
    evidence_list: list[DocumentEvidence] = []
    content_lower = content.lower()

    for pattern_def in EVIDENCE_PATTERNS:
        for pattern in pattern_def["patterns"]:
            match = re.search(pattern, content_lower)
            if match:
                matched_text = match.group(0)
                evidence_text = pattern_def["evidence_template"].format(
                    match=matched_text
                )

                evidence_list.append(
                    DocumentEvidence(
                        criterion_id=pattern_def["criterion_id"],
                        score=pattern_def["score"],
                        evidence=evidence_text,
                        confidence=pattern_def["confidence"],
                        source_file=source_file,
                    )
                )
                # Only take the first matching pattern per criterion
                break

    return evidence_list


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse_config_export(file_path: str) -> list[DocumentEvidence]:
    """Parse a UC config export or workspace description document.

    Scans the document for keyword patterns that indicate criterion evidence
    and returns DocumentEvidence objects with confidence scores in 0.6–0.85.

    Supports .txt, .json, .yaml, .yml, .md, .csv, .conf, .cfg, and .pdf files.

    Args:
        file_path: Path to the config export or workspace description file.

    Returns:
        List of DocumentEvidence objects with extracted criterion signals.
        Returns empty list for empty or unreadable files.

    Raises:
        FileNotFoundError: If the file does not exist.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    # Reject oversized documents before parsing (Guardian C2 / threat T5).
    from forge.document_ingest.cost_parser import _check_file_size
    _check_file_size(file_path)

    source_file = os.path.basename(file_path)

    content = _extract_content(file_path)

    # Empty or unreadable file → return empty list
    if not content.strip():
        return []

    return _scan_for_evidence(content, source_file)

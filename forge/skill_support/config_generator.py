"""
FORGE 2.3 — Skill Support: Config Generator

Generates the relevance-config.json file consumed by the collector CLI and
builds the fully resolved shell command for deterministic assessment execution.

The config generator is called by the Kiro Skill after the interactive probe
and validation phases complete. It serializes the results into a JSON file
that the collector can consume without re-running any detection logic.

All functions are importable without CLI context — no argparse, no sys.exit,
no interactive prompts.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Optional

from forge.models import (
    ProbeResult,
    ValidationResult,
    ServiceClassification,
    RelevanceStatus,
)
from forge.relevance_engine.classifier import classify_criterion_relevance
from forge.criteria_registry import CRITERIA_REGISTRY


def generate_relevance_config(
    probe_results: dict[str, ProbeResult],
    validation_results: dict[str, ValidationResult],
    output_dir: str = ".",
) -> str:
    """Generate a relevance-config.json file from probe and validation results.

    Produces a JSON file containing:
    - generated_at: ISO 8601 timestamp of generation
    - services: Map of service name to status, confidence, and classification
    - criteria_relevance: Map of criterion ID (e.g., "P1.1") to relevance status

    The generated file is consumed by the collector CLI via --relevance-config
    for deterministic, non-interactive scoring.

    Args:
        probe_results: Dict of service name to ProbeResult (from probe_account).
        validation_results: Dict of service name to ValidationResult (from validate_provisioned).
        output_dir: Directory to write the relevance-config.json file. Defaults to current dir.

    Returns:
        Absolute path to the written relevance-config.json file.
    """
    # Build the services section
    services: dict[str, dict] = {}
    for service_name, probe in probe_results.items():
        service_entry: dict = {
            "status": probe.classification.value,
            "confidence": 0.0,
            "classification": None,
        }

        # Add validation data if available
        validation = validation_results.get(service_name)
        if validation:
            service_entry["confidence"] = validation.confidence_score
            service_entry["classification"] = validation.classification
        elif probe.classification == ServiceClassification.PROVISIONED:
            # Provisioned but no validation data — default confidence
            service_entry["confidence"] = 0.5
            service_entry["classification"] = "moderate"

        services[service_name] = service_entry

    # Build the criteria_relevance section
    criteria_relevance: dict[str, str] = {}
    for criterion in CRITERIA_REGISTRY:
        criterion_id = f"{criterion.pillar}.{criterion.index}"
        status, _reason = classify_criterion_relevance(
            criterion, probe_results, validation_results
        )
        criteria_relevance[criterion_id] = status.value

    # Assemble the full config
    config = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "services": services,
        "criteria_relevance": criteria_relevance,
    }

    # Write JSON file
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "relevance-config.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)

    return os.path.abspath(output_path)


def build_cli_command(
    account_id: str,
    region: str,
    relevance_config_path: str,
    role_arn: Optional[str] = None,
    output_path: Optional[str] = None,
) -> str:
    """Build a fully resolved shell command for assessment execution.

    Generates the CLI command that the user can copy and execute in a terminal.
    The command includes --relevance-config pointing to the pre-computed config,
    ensuring deterministic, non-interactive execution.

    Args:
        account_id: AWS account ID (12-digit string).
        region: AWS region (e.g., "us-east-1").
        relevance_config_path: Path to the generated relevance-config.json file.
        role_arn: Optional IAM role ARN for cross-account access.
        output_path: Optional output file path. Defaults to "forge_assessment_results.json".

    Returns:
        A fully resolved shell command string ready for terminal execution.
    """
    parts = [
        "python3 -m forge.collector",
        f"--account-id {account_id}",
        f"--region {region}",
        f"--relevance-config {relevance_config_path}",
    ]

    if role_arn:
        parts.append(f"--role-arn {role_arn}")

    # Output path — default if not specified
    effective_output = output_path or "forge_assessment_results.json"
    parts.append(f"--output {effective_output}")

    return " ".join(parts)

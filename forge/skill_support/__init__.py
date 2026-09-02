"""
FORGE 2.3 — Skill Support Layer

Public API bridge between the Kiro Skill and the core FORGE engine modules.
This package provides high-level functions that the Kiro Skill calls during
interactive assessment configuration:

- probe_account: Probe an AWS account to discover provisioned services
- generate_relevance_config: Generate pre-computed relevance config JSON
- build_cli_command: Build the fully resolved assessment CLI command

All exports are importable without CLI context.
"""
from forge.skill_support.probe_runner import probe_account, validate_provisioned
from forge.skill_support.config_generator import generate_relevance_config, build_cli_command


__all__ = [
    "probe_account",
    "validate_provisioned",
    "generate_relevance_config",
    "build_cli_command",
]

"""Dimension enums and shift/floor lookup tables for the FORGE Profile Engine.

This module defines the four profile dimensions (Architecture, Workload, Industry,
AgentMaturity) as string enums, along with their corresponding shift vectors and
floor override tables used by the weight and floor resolvers.

Weights and shift tables can be overridden via forge_config/weights.yaml.
If the YAML file is missing or unreadable, hardcoded defaults are used.
"""

from enum import Enum
from pathlib import Path


class Architecture(str, Enum):
    OPEN_LAKEHOUSE = "open_lakehouse"
    SAAS_NATIVE = "saas_native"
    HYBRID = "hybrid"


class Workload(str, Enum):
    RAG_RETRIEVAL = "rag_retrieval"
    SINGLE_TOOL = "single_tool"
    MULTI_TOOL_AGENTS = "multi_tool_agents"


class Industry(str, Enum):
    GENERAL = "general"
    FINANCIAL_SERVICES = "financial_services"
    HEALTHCARE = "healthcare"
    PUBLIC_SECTOR = "public_sector"


class AgentMaturity(str, Enum):
    PILOT = "pilot"
    SINGLE_AGENT_PROD = "single_agent_prod"
    MULTI_AGENT_PROD = "multi_agent_prod"


# ---------------------------------------------------------------------------
# Default values (used as fallback when YAML config is absent)
# ---------------------------------------------------------------------------

_DEFAULT_BASE_WEIGHTS: dict[str, int] = {
    "P1": 17, "P2": 17, "P3": 8, "P4": 12,
    "P5": 11, "P6": 9, "P7": 7, "P8": 10, "P9": 9,
}

_DEFAULT_ARCHITECTURE_SHIFTS: dict[Architecture, dict[str, int]] = {
    Architecture.OPEN_LAKEHOUSE: {"P1": 0, "P2": 0, "P3": 0, "P4": 0, "P5": 0, "P6": 0, "P7": 0, "P8": 0, "P9": 0},
    Architecture.SAAS_NATIVE:    {"P1": +3, "P2": +1, "P3": -6, "P4": 0, "P5": +2, "P6": 0, "P7": 0, "P8": 0, "P9": 0},
    Architecture.HYBRID:         {"P1": +1, "P2": +1, "P3": -3, "P4": 0, "P5": +1, "P6": 0, "P7": 0, "P8": 0, "P9": 0},
}

_DEFAULT_WORKLOAD_SHIFTS: dict[Workload, dict[str, int]] = {
    Workload.RAG_RETRIEVAL:     {"P1": 0, "P2": +3, "P3": +1, "P4": 0, "P5": 0, "P6": 0, "P7": 0, "P8": -2, "P9": -2},
    Workload.SINGLE_TOOL:       {"P1": 0, "P2": 0, "P3": 0, "P4": 0, "P5": 0, "P6": 0, "P7": 0, "P8": 0, "P9": 0},
    Workload.MULTI_TOOL_AGENTS: {"P1": +1, "P2": -2, "P3": -2, "P4": 0, "P5": +2, "P6": -2, "P7": 0, "P8": +3, "P9": 0},
}

_DEFAULT_INDUSTRY_SHIFTS: dict[Industry, dict[str, int]] = {
    Industry.GENERAL:            {"P1": 0, "P2": 0, "P3": 0, "P4": 0, "P5": 0, "P6": 0, "P7": 0, "P8": 0, "P9": 0},
    Industry.FINANCIAL_SERVICES: {"P1": -3, "P2": -3, "P3": 0, "P4": +2, "P5": +2, "P6": +2, "P7": -2, "P8": 0, "P9": +2},
    Industry.HEALTHCARE:         {"P1": -4, "P2": -3, "P3": 0, "P4": +2, "P5": +3, "P6": +2, "P7": -3, "P8": 0, "P9": +3},
    Industry.PUBLIC_SECTOR:      {"P1": +2, "P2": +2, "P3": 0, "P4": +3, "P5": -2, "P6": -1, "P7": -2, "P8": -1, "P9": -1},
}

_DEFAULT_AGENT_MATURITY_SHIFTS: dict[AgentMaturity, dict[str, int]] = {
    AgentMaturity.PILOT:             {"P1": +2, "P2": +2, "P3": 0, "P4": 0, "P5": 0, "P6": 0, "P7": 0, "P8": -2, "P9": -2},
    AgentMaturity.SINGLE_AGENT_PROD: {"P1": 0, "P2": 0, "P3": 0, "P4": 0, "P5": 0, "P6": 0, "P7": 0, "P8": 0, "P9": 0},
    AgentMaturity.MULTI_AGENT_PROD:  {"P1": -3, "P2": -3, "P3": -3, "P4": 0, "P5": +1, "P6": +2, "P7": 0, "P8": +3, "P9": +3},
}

_DEFAULT_ARCHITECTURE_FLOORS: dict[Architecture, dict[str, int]] = {
    Architecture.OPEN_LAKEHOUSE: {},
    Architecture.SAAS_NATIVE:    {},
    Architecture.HYBRID:         {},
}

_DEFAULT_WORKLOAD_FLOORS: dict[Workload, dict[str, int]] = {
    Workload.RAG_RETRIEVAL:     {},
    Workload.SINGLE_TOOL:       {},
    Workload.MULTI_TOOL_AGENTS: {},
}

_DEFAULT_INDUSTRY_FLOORS: dict[Industry, dict[str, int]] = {
    Industry.GENERAL:            {},
    Industry.FINANCIAL_SERVICES: {"P6": 40, "P9": 35},
    Industry.HEALTHCARE:         {"P5": 45, "P9": 40},
    Industry.PUBLIC_SECTOR:      {},
}

_DEFAULT_AGENT_MATURITY_FLOORS: dict[AgentMaturity, dict[str, int]] = {
    AgentMaturity.PILOT:             {},
    AgentMaturity.SINGLE_AGENT_PROD: {},
    AgentMaturity.MULTI_AGENT_PROD:  {"P8": 40, "P9": 35},
}


# ---------------------------------------------------------------------------
# YAML config loader
# ---------------------------------------------------------------------------

def _load_weights_config() -> dict | None:
    """Try to load forge_config/weights.yaml, returning parsed dict or None.

    Searches for the config file relative to the project root (detected as the
    directory containing 'forge_config/' or the current working directory).
    Falls back gracefully if the file is missing, malformed, or PyYAML is not installed.
    """
    # Try multiple resolution paths for forge_config/weights.yaml
    candidates = [
        Path("forge_config/weights.yaml"),
        Path(__file__).resolve().parent.parent.parent / "forge_config" / "weights.yaml",
    ]

    config_path = None
    for candidate in candidates:
        if candidate.exists():
            config_path = candidate
            break

    if config_path is None:
        return None

    try:
        import yaml
    except ImportError:
        # PyYAML not installed — use defaults silently
        return None

    try:
        with open(config_path, "r") as f:
            return yaml.safe_load(f)
    except (OSError, yaml.YAMLError):
        # File unreadable or malformed — use defaults silently
        return None


def _build_shift_table(raw: dict, enum_class):
    """Convert a raw YAML shift dict (str keys → pillar dicts) to enum-keyed dict."""
    result = {}
    for key, pillar_shifts in raw.items():
        enum_val = enum_class(key)
        result[enum_val] = {k: int(v) for k, v in pillar_shifts.items()}
    return result


def _build_floor_table(raw: dict, enum_class):
    """Convert a raw YAML floor dict (str keys → pillar dicts) to enum-keyed dict."""
    result = {}
    for key, pillar_floors in raw.items():
        enum_val = enum_class(key)
        result[enum_val] = {k: int(v) for k, v in pillar_floors.items()} if pillar_floors else {}
    return result


def _apply_config():
    """Load YAML config and populate module-level constants.

    If YAML is available and valid, its values override the defaults.
    Otherwise, defaults are used unchanged.
    """
    global BASE_WEIGHTS
    global ARCHITECTURE_SHIFTS, WORKLOAD_SHIFTS, INDUSTRY_SHIFTS, AGENT_MATURITY_SHIFTS
    global ARCHITECTURE_FLOORS, WORKLOAD_FLOORS, INDUSTRY_FLOORS, AGENT_MATURITY_FLOORS

    # Start with defaults
    BASE_WEIGHTS = dict(_DEFAULT_BASE_WEIGHTS)
    ARCHITECTURE_SHIFTS = dict(_DEFAULT_ARCHITECTURE_SHIFTS)
    WORKLOAD_SHIFTS = dict(_DEFAULT_WORKLOAD_SHIFTS)
    INDUSTRY_SHIFTS = dict(_DEFAULT_INDUSTRY_SHIFTS)
    AGENT_MATURITY_SHIFTS = dict(_DEFAULT_AGENT_MATURITY_SHIFTS)
    ARCHITECTURE_FLOORS = dict(_DEFAULT_ARCHITECTURE_FLOORS)
    WORKLOAD_FLOORS = dict(_DEFAULT_WORKLOAD_FLOORS)
    INDUSTRY_FLOORS = dict(_DEFAULT_INDUSTRY_FLOORS)
    AGENT_MATURITY_FLOORS = dict(_DEFAULT_AGENT_MATURITY_FLOORS)

    config = _load_weights_config()
    if config is None:
        return

    # Override base weights
    if "base_weights" in config:
        BASE_WEIGHTS = {k: int(v) for k, v in config["base_weights"].items()}

    # Override shift vectors
    shifts = config.get("shifts", {})
    if "architecture" in shifts:
        ARCHITECTURE_SHIFTS = _build_shift_table(shifts["architecture"], Architecture)
    if "workload" in shifts:
        WORKLOAD_SHIFTS = _build_shift_table(shifts["workload"], Workload)
    if "industry" in shifts:
        INDUSTRY_SHIFTS = _build_shift_table(shifts["industry"], Industry)
    if "agent_maturity" in shifts:
        AGENT_MATURITY_SHIFTS = _build_shift_table(shifts["agent_maturity"], AgentMaturity)

    # Override floor tables
    floors = config.get("floors", {})
    if "architecture" in floors:
        ARCHITECTURE_FLOORS = _build_floor_table(floors["architecture"], Architecture)
    if "workload" in floors:
        WORKLOAD_FLOORS = _build_floor_table(floors["workload"], Workload)
    if "industry" in floors:
        INDUSTRY_FLOORS = _build_floor_table(floors["industry"], Industry)
    if "agent_maturity" in floors:
        AGENT_MATURITY_FLOORS = _build_floor_table(floors["agent_maturity"], AgentMaturity)


# ---------------------------------------------------------------------------
# Module-level constants — populated on import
# ---------------------------------------------------------------------------

BASE_WEIGHTS: dict[str, int] = {}
ARCHITECTURE_SHIFTS: dict[Architecture, dict[str, int]] = {}
WORKLOAD_SHIFTS: dict[Workload, dict[str, int]] = {}
INDUSTRY_SHIFTS: dict[Industry, dict[str, int]] = {}
AGENT_MATURITY_SHIFTS: dict[AgentMaturity, dict[str, int]] = {}
ARCHITECTURE_FLOORS: dict[Architecture, dict[str, int]] = {}
WORKLOAD_FLOORS: dict[Workload, dict[str, int]] = {}
INDUSTRY_FLOORS: dict[Industry, dict[str, int]] = {}
AGENT_MATURITY_FLOORS: dict[AgentMaturity, dict[str, int]] = {}

# Load config (or defaults) at module import time
_apply_config()

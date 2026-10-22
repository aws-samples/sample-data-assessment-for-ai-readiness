"""
DAFM — Relevance Configuration Loader (backward-compat shim)

This module has moved to dafm.relevance_engine.config_loader.
This shim preserves backward compatibility for existing imports.
"""
from dafm.relevance_engine.config_loader import load_relevance_config

__all__ = ["load_relevance_config"]

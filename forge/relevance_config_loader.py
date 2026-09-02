"""
FORGE 2.3 — Relevance Configuration Loader (backward-compat shim)

This module has moved to forge.relevance_engine.config_loader.
This shim preserves backward compatibility for existing imports.
"""
from forge.relevance_engine.config_loader import load_relevance_config

__all__ = ["load_relevance_config"]

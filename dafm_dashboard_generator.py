#!/usr/bin/env python3
"""Backward-compat wrapper. Use `python3 -m dafm dashboard` instead."""
from dafm.dashboard.generator import generate_dashboard
import sys
import os

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 dafm_dashboard_generator.py <results.json> [output.html]")
        sys.exit(1)
    results = sys.argv[1]
    output = sys.argv[2] if len(sys.argv) > 2 else "dafm_output/dafm_dashboard.html"
    generate_dashboard(results, output)

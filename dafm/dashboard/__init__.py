"""
DAFM — Dashboard Generator Package

Produces an interactive HTML dashboard from assessment results JSON.
"""
from dafm.dashboard.generator import generate_dashboard, generate_estate_dashboard

__all__ = ["generate_dashboard", "generate_estate_dashboard"]

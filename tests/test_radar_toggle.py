"""Tests for _generate_radar_toggle_section in dashboard generator."""

import pytest

from forge.dashboard.generator import _generate_radar_toggle_section


PILLAR_NAMES = ["P1", "P2", "P3", "P4", "P5", "P6", "P7", "P8", "P9"]


class TestRadarToggleSinglePlatform:
    """When only one platform exists, no toggle buttons should appear."""

    def test_single_platform_no_toggle(self):
        combined = {p: 50.0 for p in PILLAR_NAMES}
        platform_scores = {"aws": {p: 50.0 for p in PILLAR_NAMES}}
        result = _generate_radar_toggle_section(combined, platform_scores, PILLAR_NAMES)

        # Should render plain SVG without toggle controls
        assert "radar-toggle" not in result
        assert "radar-btn" not in result
        assert "showRadar" not in result
        # Should still have a radar SVG
        assert "<svg" in result

    def test_empty_platform_scores_no_toggle(self):
        combined = {p: 60.0 for p in PILLAR_NAMES}
        platform_scores = {}
        result = _generate_radar_toggle_section(combined, platform_scores, PILLAR_NAMES)

        assert "radar-toggle" not in result
        assert "<svg" in result


class TestRadarToggleMultiPlatform:
    """When multiple platforms exist, toggle buttons and multiple radars should appear."""

    def test_two_platforms_shows_toggle(self):
        combined = {p: 60.0 for p in PILLAR_NAMES}
        platform_scores = {
            "aws": {p: 70.0 for p in PILLAR_NAMES},
            "databricks": {p: 50.0 for p in PILLAR_NAMES},
        }
        result = _generate_radar_toggle_section(combined, platform_scores, PILLAR_NAMES)

        # Toggle buttons present
        assert "radar-toggle" in result
        assert "Combined" in result
        assert "AWS" in result
        assert "Databricks" in result

    def test_combined_is_default_active(self):
        combined = {p: 55.0 for p in PILLAR_NAMES}
        platform_scores = {
            "aws": {p: 65.0 for p in PILLAR_NAMES},
            "databricks": {p: 45.0 for p in PILLAR_NAMES},
        }
        result = _generate_radar_toggle_section(combined, platform_scores, PILLAR_NAMES)

        # Combined button has 'active' class
        assert 'class="radar-btn active" onclick="showRadar(\'combined\')"' in result
        # Combined radar view is visible (no display:none)
        assert 'id="radar-combined" class="radar-view active"' in result

    def test_platform_radars_initially_hidden(self):
        combined = {p: 55.0 for p in PILLAR_NAMES}
        platform_scores = {
            "aws": {p: 65.0 for p in PILLAR_NAMES},
            "databricks": {p: 45.0 for p in PILLAR_NAMES},
        }
        result = _generate_radar_toggle_section(combined, platform_scores, PILLAR_NAMES)

        # Platform radars hidden by default
        assert 'id="radar-aws" class="radar-view" style="display:none"' in result
        assert 'id="radar-databricks" class="radar-view" style="display:none"' in result

    def test_javascript_toggle_function_present(self):
        combined = {p: 55.0 for p in PILLAR_NAMES}
        platform_scores = {
            "aws": {p: 65.0 for p in PILLAR_NAMES},
            "databricks": {p: 45.0 for p in PILLAR_NAMES},
        }
        result = _generate_radar_toggle_section(combined, platform_scores, PILLAR_NAMES)

        assert "function showRadar(platform)" in result
        assert "getElementById('radar-' + platform)" in result

    def test_three_radar_svgs_generated(self):
        combined = {p: 55.0 for p in PILLAR_NAMES}
        platform_scores = {
            "aws": {p: 65.0 for p in PILLAR_NAMES},
            "databricks": {p: 45.0 for p in PILLAR_NAMES},
        }
        result = _generate_radar_toggle_section(combined, platform_scores, PILLAR_NAMES)

        # Should have 3 separate SVG blocks (combined, aws, databricks)
        assert result.count("<svg") == 3

    def test_pillar_scores_reflected_in_svg(self):
        combined = {"P1": 80.0, "P2": 40.0, "P3": 60.0, "P4": 50.0,
                    "P5": 70.0, "P6": 30.0, "P7": 90.0, "P8": 55.0, "P9": 65.0}
        platform_scores = {
            "aws": {"P1": 90.0, "P2": 50.0, "P3": 70.0, "P4": 60.0,
                    "P5": 80.0, "P6": 40.0, "P7": 95.0, "P8": 65.0, "P9": 75.0},
            "databricks": {"P1": 60.0, "P2": 30.0, "P3": 50.0, "P4": 40.0,
                           "P5": 55.0, "P6": 20.0, "P7": 80.0, "P8": 40.0, "P9": 50.0},
        }
        result = _generate_radar_toggle_section(combined, platform_scores, PILLAR_NAMES)

        # Score labels should appear in SVG text elements
        assert "80%" in result  # P1 combined
        assert "90%" in result  # P1 AWS
        assert "60%" in result  # P1 Databricks

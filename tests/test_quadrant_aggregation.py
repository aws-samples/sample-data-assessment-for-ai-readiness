"""Tests for quadrant pillar TCO aggregation, compliance share, and the
visible-failure behaviour of the dashboard quadrant section."""

from pathlib import Path

from dafm.dashboard import generator
from dafm.dashboard.generator import (
    _aggregate_pillar_tco,
    _pillar_compliance_share,
    generate_dashboard,
)

EXAMPLE = Path(__file__).resolve().parent.parent / "examples" / "sample_tagged_assessment.json"


def _crit(level: str, compliance=None) -> dict:
    return {
        "cost": level,
        "operational_overhead": level,
        "severity": level,
        "compliance": compliance or [],
    }


class TestPillarTcoMean:
    def test_mean_and_max(self):
        pillar = {"criteria": [_crit("low"), _crit("low"), _crit("high")]}
        mean, mx = _aggregate_pillar_tco(pillar)
        assert round(mean, 2) == 2.33
        assert mx == 5

    def test_untagged_pillar_falls_back_to_three(self):
        assert _aggregate_pillar_tco({"criteria": []}) == (3.0, 3)
        assert _aggregate_pillar_tco({"criteria": [{"name": "x"}]}) == (3.0, 3)

    def test_criteria_without_cost_are_skipped(self):
        pillar = {"criteria": [_crit("high"), {"severity": "high"}]}
        assert _aggregate_pillar_tco(pillar) == (5.0, 5)


class TestComplianceShare:
    def test_two_of_four_is_fifty_percent(self):
        pillar = {
            "criteria": [
                _crit("low", ["GDPR"]),
                _crit("low", ["SOC2", "HIPAA"]),
                _crit("low"),
                _crit("low"),
            ]
        }
        assert _pillar_compliance_share(pillar) == 50.0

    def test_empty_pillar_is_zero(self):
        assert _pillar_compliance_share({"criteria": []}) == 0.0


class TestQuadrantFailureVisible:
    def test_dashboard_renders_unavailable_card_when_quadrant_raises(
        self, monkeypatch, tmp_path, caplog
    ):
        def boom(pillars, scoring):
            raise RuntimeError("boom")

        monkeypatch.setattr(generator, "_generate_quadrant_section", boom)
        out = tmp_path / "dash.html"
        with caplog.at_level("ERROR", logger="dafm.dashboard.generator"):
            generate_dashboard(str(EXAMPLE), str(out))

        html = out.read_text()
        assert "AI-Readiness Quadrant unavailable: tag data could not be rendered." in html
        assert "Criteria Detail" in html  # core dashboard still rendered
        assert any("could not be rendered" in r.getMessage() for r in caplog.records)

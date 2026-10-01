"""Tests for the FORGE tag taxonomy, TCO indicator, model round-trip, and
the additive AI-readiness quadrant dashboard section."""

from forge.dashboard.generator import _generate_quadrant_section
from forge.models import CriterionDefinition, CriterionType, ForgeAssessmentResult
from forge.taxonomy_loader import (
    get_pillar_tags,
    list_frameworks,
    list_tensions,
    list_vectors,
    load_taxonomy,
)
from forge.tco import compute_tco


class TestComputeTco:
    """The TCO indicator must match the taxonomy formula exactly."""

    def test_all_low_is_one(self):
        assert compute_tco("low", "low", "low") == 1

    def test_all_high_is_five(self):
        assert compute_tco("high", "high", "high") == 5

    def test_medium_low_high_is_two(self):
        assert compute_tco("medium", "low", "high") == 2

    def test_unscored_returns_zero(self):
        assert compute_tco("", "", "") == 0
        assert compute_tco("", "", "high") == 0

    def test_result_always_clamped_to_scale(self):
        for cost in ("low", "medium", "high"):
            for overhead in ("low", "medium", "high"):
                for severity in ("low", "medium", "high"):
                    assert 1 <= compute_tco(cost, overhead, severity) <= 5


class TestFromDictRoundTrip:
    """Old JSON (without taxonomy fields) must still load, and new fields
    must round-trip through from_dict."""

    def _make_payload(self, criterion: dict) -> dict:
        return {
            "metadata": {"customer": "acme"},
            "pillars": [
                {
                    "code": "P1",
                    "name": "Agent Access & Discovery",
                    "raw_score": 50.0,
                    "relevant_count": 1,
                    "not_applicable_count": 0,
                    "undetermined_count": 0,
                    "criteria": [criterion],
                }
            ],
            "summary": {"forge_score": 50},
        }

    def test_legacy_criterion_without_new_fields_loads(self):
        payload = self._make_payload({
            "index": 1,
            "name": "MCP endpoint exposed",
            "score": 1.0,
            "relevance_status": "relevant",
            "confidence_score": 0.9,
            "evidence": "found",
            "criterion_type": "binary",
        })
        result = ForgeAssessmentResult.from_dict(payload)
        c = result.pillars[0].criteria[0]
        # Defaults applied, no error.
        assert c.cost == ""
        assert c.operational_overhead == ""
        assert c.severity == ""
        assert c.tension == ""
        assert c.vectors == []
        assert c.compliance == []

    def test_criterion_with_new_fields_round_trips(self):
        payload = self._make_payload({
            "index": 2,
            "name": "Fine-grained row filter",
            "score": 0.5,
            "relevance_status": "relevant",
            "confidence_score": 0.8,
            "evidence": "partial",
            "criterion_type": "analog",
            "cost": "medium",
            "operational_overhead": "low",
            "severity": "high",
            "tension": "portable_vs_maturity",
            "vectors": ["fine_grained_access_control", "governance"],
            "compliance": ["GDPR", "HIPAA"],
        })
        result = ForgeAssessmentResult.from_dict(payload)
        c = result.pillars[0].criteria[0]
        assert c.cost == "medium"
        assert c.operational_overhead == "low"
        assert c.severity == "high"
        assert c.tension == "portable_vs_maturity"
        assert c.vectors == ["fine_grained_access_control", "governance"]
        assert c.compliance == ["GDPR", "HIPAA"]
        # And the carried TCO inputs recompute correctly.
        assert compute_tco(c.cost, c.operational_overhead, c.severity) == 2


class TestCriterionDefinitionBackwardCompatible:
    """Existing positional/keyword construction must keep working."""

    def test_minimal_definition_defaults(self):
        d = CriterionDefinition(
            pillar="P1", index=1, name="x", criterion_type=CriterionType.BINARY
        )
        assert d.cost == ""
        assert d.vectors == []
        assert d.compliance == []


class TestTaxonomyLoader:
    def test_loads_version_and_sections(self):
        tax = load_taxonomy()
        assert tax.get("version") == "0.2"
        assert len(list_vectors()) == 9
        assert len(list_tensions()) == 6
        assert "GDPR" in list_frameworks()
        assert get_pillar_tags("P1")["primary_vector"] == "interoperable"

    def test_unknown_pillar_returns_empty(self):
        assert get_pillar_tags("P99") == {}


class TestQuadrantSection:
    """The quadrant section is additive and renders plottable bubbles."""

    def _scoring(self) -> dict:
        pillar_scores = {}
        for i in range(1, 10):
            pillar_scores[f"P{i}"] = {
                "score_percent": 10 * i,
                "met": i,
                "total": 12,
            }
        return {"pillar_scores": pillar_scores, "coverage_multiplier": 1.0}

    def _pillars(self) -> list:
        return [
            {
                "code": f"P{i}",
                "name": f"Pillar {i}",
                "total": 12,
                "criteria": [
                    {
                        "index": 1,
                        "name": "c",
                        "cost": "high",
                        "operational_overhead": "high",
                        "severity": "high",
                        "vectors": ["governance"],
                        "tension": "trust_vs_velocity",
                        "compliance": ["SOC2"],
                    }
                ],
            }
            for i in range(1, 10)
        ]

    def test_renders_svg_and_filters(self):
        html = _generate_quadrant_section(self._pillars(), self._scoring())
        assert "AI-Readiness Quadrant" in html
        assert '<svg id="quadrant-svg"' in html
        assert 'id="q-vector"' in html
        assert 'id="q-tension"' in html
        assert 'id="q-framework"' in html
        # All nine pillars present in the embedded data.
        for i in range(1, 10):
            assert f"P{i}" in html

    def test_handles_criteria_without_tags(self):
        pillars = [
            {"code": "P1", "name": "P1", "total": 5, "criteria": []},
        ]
        scoring = {"pillar_scores": {"P1": {"score_percent": 42, "met": 2, "total": 5}}}
        html = _generate_quadrant_section(pillars, scoring)
        # Neutral fallback keeps the pillar plottable.
        assert "quadrant-svg" in html
        assert "P1" in html

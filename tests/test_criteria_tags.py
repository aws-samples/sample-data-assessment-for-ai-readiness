"""Conformance tests for the reviewed probe-level criteria tags
(dafm_config/criteria_tags.yaml) and their wiring into the criteria registry."""

from pathlib import Path

import yaml

from dafm.criteria_registry import CRITERIA_REGISTRY, get_criterion
from dafm.taxonomy_loader import load_taxonomy
from dafm.tco import compute_tco

TAGS_PATH = Path(__file__).resolve().parent.parent / "dafm_config" / "criteria_tags.yaml"
LEVELS = {"low", "medium", "high"}


def _load_tags() -> dict:
    with open(TAGS_PATH, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _registry_keys() -> set:
    return {f"{c.pillar}.{c.index}" for c in CRITERIA_REGISTRY}


class TestTagCoverage:
    def test_every_criterion_has_a_tag_entry(self):
        assert _registry_keys() - set(_load_tags()) == set()

    def test_no_orphan_tag_entries(self):
        assert set(_load_tags()) - _registry_keys() == set()

    def test_exactly_142_entries(self):
        assert len(_load_tags()) == 142


class TestTagValues:
    def test_values_are_in_taxonomy_sets(self):
        taxonomy = load_taxonomy()
        vectors = set(taxonomy["readiness_vectors"])
        tensions = set(taxonomy["tensions"])
        frameworks = set(taxonomy["compliance_frameworks"]["catalog"])
        for key, entry in _load_tags().items():
            assert entry["vectors"], key
            assert set(entry["vectors"]) <= vectors, key
            assert entry["tension"] in tensions, key
            assert set(entry["compliance"]) <= frameworks, key
            assert entry["cost"] in LEVELS, key
            assert entry["operational_overhead"] in LEVELS, key
            assert entry["severity"] in LEVELS, key


class TestRegistryWiring:
    def test_known_entries_carry_tags(self):
        p5_16 = get_criterion("P5", 16)
        assert p5_16.tension == "centralization_vs_federation"
        assert p5_16.severity == "high"
        p3_14 = get_criterion("P3", 14)
        assert "GDPR" in p3_14.compliance

    def test_every_registry_criterion_is_tagged(self):
        for c in CRITERIA_REGISTRY:
            key = f"{c.pillar}.{c.index}"
            assert c.vectors and c.tension and c.cost and c.severity, key
            assert c.operational_overhead, key

    def test_registry_matches_tag_file(self):
        tags = _load_tags()
        for c in CRITERIA_REGISTRY:
            entry = tags[f"{c.pillar}.{c.index}"]
            assert c.vectors == entry["vectors"]
            assert c.tension == entry["tension"]
            assert c.compliance == entry["compliance"]


class TestTcoSpread:
    def test_tco_values_in_range_and_varied(self):
        values = {
            key: compute_tco(e["cost"], e["operational_overhead"], e["severity"])
            for key, e in _load_tags().items()
        }
        assert all(1 <= v <= 5 for v in values.values())
        assert len(set(values.values())) >= 4, "tag file is too flat to be informative"

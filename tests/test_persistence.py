"""Tests for forge/profile_engine/persistence.py — YAML read/write and lock."""

from pathlib import Path

import pytest
import yaml

from forge.profile_engine import ForgeProfile
from forge.profile_engine.dimensions import (
    AgentMaturity,
    Architecture,
    Industry,
    Workload,
)
from forge.profile_engine.persistence import (
    ProfileLockError,
    ProfileNotFoundError,
    is_locked,
    load_profile,
    save_profile,
)


@pytest.fixture
def sample_profile() -> ForgeProfile:
    return ForgeProfile(
        architecture=Architecture.OPEN_LAKEHOUSE,
        workload=Workload.MULTI_TOOL_AGENTS,
        industry=Industry.FINANCIAL_SERVICES,
        agent_maturity=AgentMaturity.SINGLE_AGENT_PROD,
    )


@pytest.fixture
def profile_path(tmp_path: Path) -> Path:
    return tmp_path / "forge_profile.yaml"


class TestSaveProfile:
    def test_writes_yaml_with_locked_true(
        self, sample_profile: ForgeProfile, profile_path: Path
    ):
        save_profile(sample_profile, profile_path)

        data = yaml.safe_load(profile_path.read_text())
        assert data["locked"] is True
        assert "locked_at" in data
        assert data["profile"]["architecture"] == "open_lakehouse"
        assert data["profile"]["workload"] == "multi_tool_agents"
        assert data["profile"]["industry"] == "financial_services"
        assert data["profile"]["agent_maturity"] == "single_agent_prod"

    def test_raises_profile_lock_error_when_already_locked(
        self, sample_profile: ForgeProfile, profile_path: Path
    ):
        save_profile(sample_profile, profile_path)

        with pytest.raises(ProfileLockError):
            save_profile(sample_profile, profile_path)

    def test_locked_at_is_iso_utc_format(
        self, sample_profile: ForgeProfile, profile_path: Path
    ):
        save_profile(sample_profile, profile_path)

        data = yaml.safe_load(profile_path.read_text())
        locked_at = data["locked_at"]
        # Should end with Z and be parseable
        assert locked_at.endswith("Z")
        assert "T" in locked_at


class TestLoadProfile:
    def test_loads_saved_profile_correctly(
        self, sample_profile: ForgeProfile, profile_path: Path
    ):
        save_profile(sample_profile, profile_path)
        loaded = load_profile(profile_path)

        assert loaded.architecture == Architecture.OPEN_LAKEHOUSE
        assert loaded.workload == Workload.MULTI_TOOL_AGENTS
        assert loaded.industry == Industry.FINANCIAL_SERVICES
        assert loaded.agent_maturity == AgentMaturity.SINGLE_AGENT_PROD

    def test_raises_profile_not_found_error_for_missing_file(
        self, profile_path: Path
    ):
        with pytest.raises(ProfileNotFoundError):
            load_profile(profile_path)

    def test_round_trip_preserves_all_dimensions(self, profile_path: Path):
        """Save then load should produce identical profile values."""
        original = ForgeProfile(
            architecture=Architecture.HYBRID,
            workload=Workload.RAG_RETRIEVAL,
            industry=Industry.HEALTHCARE,
            agent_maturity=AgentMaturity.MULTI_AGENT_PROD,
        )
        save_profile(original, profile_path)
        loaded = load_profile(profile_path)

        assert loaded.architecture == original.architecture
        assert loaded.workload == original.workload
        assert loaded.industry == original.industry
        assert loaded.agent_maturity == original.agent_maturity


class TestIsLocked:
    def test_returns_false_when_file_does_not_exist(self, profile_path: Path):
        assert is_locked(profile_path) is False

    def test_returns_true_after_save(
        self, sample_profile: ForgeProfile, profile_path: Path
    ):
        save_profile(sample_profile, profile_path)
        assert is_locked(profile_path) is True

    def test_returns_false_for_unlocked_yaml(self, profile_path: Path):
        data = {
            "profile": {
                "architecture": "hybrid",
                "workload": "single_tool",
                "industry": "general",
                "agent_maturity": "pilot",
            },
            "locked": False,
        }
        profile_path.write_text(yaml.dump(data))
        assert is_locked(profile_path) is False

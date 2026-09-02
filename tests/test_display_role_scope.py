"""Tests for display_role_scope() function in forge.collector."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from forge.collector import display_role_scope, _ROLE_SCOPE_ENTRIES, _SECURITY_NOTE


def test_display_role_scope_prints_all_9_entries(capsys):
    """display_role_scope prints a numbered list of exactly 9 pillar scopes."""
    display_role_scope()
    captured = capsys.readouterr()
    output = captured.out

    # Should have 9 numbered entries
    for i in range(1, 10):
        assert f" {i}. " in output, f"Missing entry {i}"


def test_display_role_scope_no_broad_prefix(capsys):
    """No [BROAD] prefix since we use specific actions, not wildcards."""
    display_role_scope()
    captured = capsys.readouterr()
    output = captured.out

    assert "[BROAD]" not in output


def test_display_role_scope_no_deny_section(capsys):
    """No HARD DENY section — least-privilege means deny is unnecessary."""
    display_role_scope()
    captured = capsys.readouterr()
    output = captured.out

    assert "HARD DENY" not in output


def test_display_role_scope_contains_security_note(capsys):
    """Output includes the least-privilege security note."""
    display_role_scope()
    captured = capsys.readouterr()
    output = captured.out

    assert "Least-privilege" in output or "least-privilege" in output


def test_display_role_scope_contains_header(capsys):
    """Output includes the header."""
    display_role_scope()
    captured = capsys.readouterr()
    output = captured.out

    assert "FORGE-Assessment-Role Permission Summary" in output


def test_display_role_scope_entry_content(capsys):
    """Each entry matches its expected label and key actions."""
    display_role_scope()
    captured = capsys.readouterr()
    output = captured.out

    for label, actions in _ROLE_SCOPE_ENTRIES:
        assert label in output, f"Missing label: {label}"
        # Check that at least the first action pattern appears
        first_action = actions.split(",")[0].strip()
        assert first_action in output, f"Missing action: {first_action}"


def test_role_scope_entries_has_9_items():
    """The scope entries list contains exactly 9 pillar statements."""
    assert len(_ROLE_SCOPE_ENTRIES) == 9


def test_display_role_scope_uses_specific_actions(capsys):
    """Actions are specific (no wildcards like Get* or List*)."""
    display_role_scope()
    captured = capsys.readouterr()
    output = captured.out

    # The output should not contain wildcard patterns like "Get*" or "List*"
    # (specific actions like GetDatabases are fine)
    lines = output.split("\n")
    for line in lines:
        if line.strip().startswith(tuple(str(i) for i in range(1, 10))):
            # This is an entry line — check no bare wildcards
            assert "Get*" not in line, f"Wildcard found: {line}"
            assert "List*" not in line, f"Wildcard found: {line}"
            assert "Describe*" not in line, f"Wildcard found: {line}"


def test_display_role_scope_does_not_raise():
    """display_role_scope is informational and should never raise."""
    display_role_scope()

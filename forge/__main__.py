"""
FORGE 2.3 Assessment Workbench — CLI Entry Point

Usage:
    python3 -m forge profile declare --architecture open_lakehouse --workload multi_tool_agents \
        --industry healthcare --agent-maturity single_agent_prod

    python3 -m forge assess --account-id 123456789012 --region us-east-1 [--show-delta]

Two subcommands:
    1. profile declare — Declare and lock a FORGE Profile for the engagement.
    2. assess — Run a FORGE assessment using the locked profile.

All configuration comes from command-line flags — no interactive prompts.
"""
import argparse
import json
import re
import sys

from forge.collector import run_assessment, serialize_result, VERSION
from forge.profile_engine import (
    Architecture,
    ForgeProfile,
    Industry,
    AgentMaturity,
    ProfileLockError,
    ProfileNotFoundError,
    Workload,
    is_locked,
    load_profile,
    lock_profile,
)
from forge.relevance_engine.config_loader import load_relevance_config


def _validate_account_id(value: str) -> str:
    """Validate that account ID is exactly 12 digits."""
    if not re.match(r"^\d{12}$", value):
        raise argparse.ArgumentTypeError(
            f"Account ID must be exactly 12 digits, got: '{value}'"
        )
    return value


def _check_removed_track_arg(argv: list[str]) -> None:
    """Check if the user passed the removed --track argument and show migration message."""
    for arg in argv:
        if arg == "--track" or arg.startswith("--track="):
            print(
                "Error: The --track option has been replaced by FORGE Profile declaration. "
                "Use `forge profile declare` to set up a profile.",
                file=sys.stderr,
            )
            sys.exit(1)


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser with subcommands for FORGE 2.3 CLI."""
    parser = argparse.ArgumentParser(
        prog="forge",
        description="FORGE 2.3 Assessment Workbench — assess AWS accounts using FORGE Profiles.",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # --- profile declare subcommand ---
    profile_parser = subparsers.add_parser(
        "profile", help="Manage FORGE Profile"
    )
    profile_subparsers = profile_parser.add_subparsers(
        dest="profile_action", help="Profile actions"
    )

    declare_parser = profile_subparsers.add_parser(
        "declare", help="Declare and lock a FORGE Profile for this engagement"
    )
    declare_parser.add_argument(
        "--architecture",
        required=True,
        choices=[a.value for a in Architecture],
        help="Architecture dimension: open_lakehouse, saas_native, or hybrid",
    )
    declare_parser.add_argument(
        "--workload",
        required=True,
        choices=[w.value for w in Workload],
        help="Workload dimension: rag_retrieval, single_tool, or multi_tool_agents",
    )
    declare_parser.add_argument(
        "--industry",
        required=True,
        choices=[i.value for i in Industry],
        help="Industry dimension: general, financial_services, healthcare, or public_sector",
    )
    declare_parser.add_argument(
        "--agent-maturity",
        required=True,
        choices=[m.value for m in AgentMaturity],
        help="Agent maturity dimension: pilot, single_agent_prod, or multi_agent_prod",
    )

    # --- assess subcommand ---
    assess_parser = subparsers.add_parser(
        "assess", help="Run a FORGE assessment against an AWS account"
    )
    assess_parser.add_argument(
        "--account-id",
        required=True,
        type=_validate_account_id,
        help="Target AWS account ID (exactly 12 digits)",
    )
    assess_parser.add_argument(
        "--region",
        required=True,
        help="AWS region to assess (e.g., us-east-1)",
    )
    assess_parser.add_argument(
        "--customer-name",
        default="Assessment Target",
        help="Display name for the assessment target (default: 'Assessment Target')",
    )
    assess_parser.add_argument(
        "--profile",
        default=None,
        help="AWS profile name from ~/.aws/credentials (e.g., 'default', 'dev')",
    )
    assess_parser.add_argument(
        "--role-arn",
        default=None,
        help="IAM role ARN for cross-account assessment (optional)",
    )
    assess_parser.add_argument(
        "--external-id",
        default=None,
        help="External ID for confused-deputy protection (optional, used with --role-arn)",
    )
    assess_parser.add_argument(
        "--relevance-config",
        default=None,
        help="Path to pre-computed relevance config JSON from Kiro Skill (skips detection phases)",
    )
    assess_parser.add_argument(
        "--output",
        default="forge_output/assessments/forge_assessment_results.json",
        help="Output file path for assessment results JSON (default: forge_output/assessments/forge_assessment_results.json)",
    )
    assess_parser.add_argument(
        "--show-delta",
        action="store_true",
        default=False,
        help="Display delta comparison with the previous assessment after scoring",
    )

    # --- dashboard subcommand ---
    dashboard_parser = subparsers.add_parser(
        "dashboard", help="Generate an HTML dashboard from assessment results JSON"
    )
    dashboard_parser.add_argument(
        "results_file",
        help="Path to assessment results JSON file",
    )
    dashboard_parser.add_argument(
        "--output",
        default="forge_output/forge_dashboard.html",
        help="Output HTML file path (default: forge_output/forge_dashboard.html)",
    )

    return parser


def _handle_profile_declare(args) -> None:
    """Handle the 'profile declare' subcommand."""
    profile = ForgeProfile(
        architecture=Architecture(args.architecture),
        workload=Workload(args.workload),
        industry=Industry(args.industry),
        agent_maturity=AgentMaturity(args.agent_maturity),
    )

    try:
        lock_profile(profile)
    except ProfileLockError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    print("FORGE Profile declared and locked for this engagement:")
    print(f"  Architecture:   {profile.architecture.value}")
    print(f"  Workload:       {profile.workload.value}")
    print(f"  Industry:       {profile.industry.value}")
    print(f"  Agent Maturity: {profile.agent_maturity.value}")
    print(f"\nProfile saved to forge_output/forge_profile.yaml")


def _handle_assess(args) -> None:
    """Handle the 'assess' subcommand."""
    # Requirement 7.4: Reject assessment if no profile declared
    try:
        forge_profile = load_profile()
    except ProfileNotFoundError:
        print(
            "Error: No FORGE Profile declared. You must declare a profile before running "
            "an assessment.\n\n"
            "  forge profile declare --architecture <value> --workload <value> "
            "--industry <value> --agent-maturity <value>\n\n"
            "Run `forge profile declare --help` for valid dimension values.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Load relevance config if provided
    relevance_config = None
    if args.relevance_config:
        try:
            relevance_config = load_relevance_config(args.relevance_config)
        except (FileNotFoundError, ValueError) as e:
            print(f"Error loading relevance config: {e}", file=sys.stderr)
            sys.exit(1)

    # Run the assessment
    try:
        result = run_assessment(
            account_id=args.account_id,
            region=args.region,
            customer_name=args.customer_name,
            relevance_config=relevance_config,
            profile_name=args.profile,
        )
    except Exception as e:
        print(f"Assessment failed: {e}", file=sys.stderr)
        sys.exit(1)

    # Serialize and write output
    output = serialize_result(result)
    output_path = args.output

    try:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, default=str)
    except OSError as e:
        print(f"Error writing output file: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"FORGE 2.3 Assessment Complete")
    print(f"  Score: {result.summary['forge_score']} ({result.summary['readiness_band']})")
    print(f"  Profile: {forge_profile.architecture.value} / {forge_profile.workload.value} / "
          f"{forge_profile.industry.value} / {forge_profile.agent_maturity.value}")
    print(f"  Output: {output_path}")

    # Emit a SHA-256 checksum of the output so integrity can be verified out-of-band
    # (see docs/FORGE_Threat_Model.md, T13/WI-7). Output is unsigned — regenerate it
    # rather than trusting a copy from a shared or network location.
    try:
        import hashlib
        with open(output_path, "rb") as f:
            digest = hashlib.sha256(f.read()).hexdigest()
        print(f"  SHA-256: {digest}")
        print("  Note: output is unsigned; contains account metadata. Do not share publicly.")
    except OSError:
        pass

    # Show delta if requested
    if args.show_delta:
        _display_delta()


def _handle_dashboard(args) -> None:
    """Handle the 'dashboard' subcommand."""
    from forge.dashboard.generator import generate_dashboard
    generate_dashboard(args.results_file, args.output)


def _display_delta() -> None:
    """Display delta comparison with the previous assessment."""
    from forge.delta_engine import compute_delta

    delta = compute_delta()

    if not delta.available:
        print("\n  Delta: Insufficient history for comparison (need at least 2 assessments)")
        return

    # Format score delta with direction indicator
    sign = "+" if delta.score_delta > 0 else ""
    print(f"\n  Delta: {sign}{delta.score_delta} pts")
    print(f"    Improved: {delta.improved_count} pillars")
    print(f"    Regressed: {delta.regressed_count} pillars")

    if delta.band_transition:
        direction = "↑" if delta.band_transition.direction == "upgrade" else "↓"
        print(f"    Band: {delta.band_transition.previous_band} → "
              f"{delta.band_transition.current_band} {direction}")

    # Show per-pillar deltas
    for pd in delta.pillar_deltas:
        if pd.classification == "unchanged":
            continue
        indicator = "▲" if pd.classification == "improvement" else "▼"
        sign = "+" if pd.delta > 0 else ""
        print(f"    {pd.pillar}: {sign}{pd.delta} {indicator}")


def main():
    """Main CLI entry point."""
    # Check for removed --track argument before parsing
    _check_removed_track_arg(sys.argv[1:])

    # Ensure forge_output/ directory exists
    import os
    os.makedirs("forge_output/assessments", exist_ok=True)
    os.makedirs("forge_output/roadmaps", exist_ok=True)

    parser = build_parser()
    args = parser.parse_args()

    if args.command == "profile":
        if args.profile_action == "declare":
            _handle_profile_declare(args)
        else:
            parser.parse_args(["profile", "--help"])
    elif args.command == "assess":
        _handle_assess(args)
    elif args.command == "dashboard":
        _handle_dashboard(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()

"""Command dispatch for LAEW operators and the local Workbench launcher."""

import argparse
from pathlib import Path
import sys

from laew.logging_config import configure_logging
from laew.manifest import ManifestError, load_manifest


_OPERATOR_COMMANDS = {"status", "telemetry", "backup", "restore", "retention"}

def cmd_check(args) -> int:
    """
    Validate system manifest and verify workspace configuration.

    Returns:
        0 if all checks pass, 1 if errors found
    """
    manifest_path = Path(args.manifest)

    print(f"Validating manifest: {manifest_path}")
    print("-" * 60)

    # Load and validate manifest
    try:
        manifest = load_manifest(manifest_path)
        print(f"[OK] Manifest loaded successfully (version {manifest.get('version', 'unknown')})")
    except FileNotFoundError:
        print(f"[FAIL] Manifest file not found: {manifest_path}")
        return 1
    except ManifestError as e:
        print(f"[FAIL] Manifest validation failed: {e}")
        return 1
    except Exception as e:
        print(f"[FAIL] Failed to load manifest: {e}")
        return 1

    # Validate workspace structure
    workspace = manifest.get("workspace", {})
    root = workspace.get("root", ".")
    allowed_paths = workspace.get("allowed_paths", [])
    restricted_paths = workspace.get("restricted_paths", [])

    print(f"\nWorkspace Configuration:")
    print(f"  Root: {root}")
    print(f"  Allowed paths: {len(allowed_paths)}")
    print(f"  Restricted paths: {len(restricted_paths)}")

    # Check allowed paths exist
    print(f"\nAllowed Paths:")
    for path in allowed_paths:
        full_path = Path(root) / path
        if full_path.exists():
            print(f"  [OK] {path}")
        else:
            print(f"  [X] {path} (not found)")

    # Check restricted paths
    print(f"\nRestricted Paths:")
    for path in restricted_paths:
        full_path = Path(root) / path
        if full_path.exists():
            print(f"  [!] {path} (exists, restricted)")
        else:
            print(f"  [ ] {path} (not present)")

    # Validate tool registry
    tools_section = manifest.get("tools", {})
    categories = tools_section.get("categories", {})

    print(f"\nTool Registry:")
    for category, config in categories.items():
        policy = config.get("policy", "unknown")
        allowed = config.get("allowed_operations", [])
        require_approval = config.get("require_user_approval", [])
        forbidden = config.get("forbidden_operations", config.get("forbidden_patterns", []))

        print(f"  {category}:")
        print(f"    Policy: {policy}")
        print(f"    Allowed operations: {len(allowed)}")
        if require_approval:
            print(f"    Requires approval: {len(require_approval)}")
        if forbidden:
            print(f"    Forbidden: {len(forbidden)}")

    # Validate model roles
    models = manifest.get("models", {})
    roles = models.get("roles", {})

    print(f"\nModel Roles:")
    for role_name, role_config in roles.items():
        description = role_config.get("description", "")
        context_budget = role_config.get("context_budget", {})
        total_budget = context_budget.get("total", "unlimited")

        print(f"  {role_name}:")
        if description:
            print(f"    Description: {description[:60]}...")
        if total_budget != "unlimited":
            print(f"    Context budget: {total_budget} tokens")

    print("\n" + "-" * 60)
    print("[OK] All checks passed")
    return 0


def cmd_ui(args) -> int:
    """Start the loopback-only browser workspace."""
    from laew.web import serve

    try:
        serve(
            args.manifest,
            args.port,
            open_browser=not args.no_browser,
            projects_root=args.projects_root,
            workspace_root=args.workspace_root,
        )
    except OSError as e:
        print(f"[FAIL] Could not start LAEW UI: {e}")
        return 1
    return 0


def main() -> int:
    """Main CLI entry point."""
    if len(sys.argv) > 1 and sys.argv[1] in _OPERATOR_COMMANDS:
        from laew.operator_cli import dispatch
        from laew.security.protected_profile import read_telemetry_root
        return dispatch(sys.argv[1:], telemetry_root_resolver=read_telemetry_root)
    configure_logging()  # app-level logger (console stderr), Phase 3
    parser = argparse.ArgumentParser(
        prog="laew",
        description="LAEW Operator CLI",
    )

    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 0.1.0",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    subparsers.add_parser("telemetry", help="List and inspect retained telemetry runs")
    subparsers.add_parser("backup", help="Inspect backup inventory and archived generations")
    subparsers.add_parser("restore", help="Verify or publish an isolated recovery target")
    subparsers.add_parser("status", help="Inspect operational readiness without starting services")
    subparsers.add_parser("retention", help="Review or apply telemetry and session retention")

    check_parser = subparsers.add_parser(
        "check",
        help="Validate system manifest and workspace configuration",
    )
    check_parser.add_argument(
        "--manifest",
        default="manifests/SYSTEM_MANIFEST.yaml",
        help="Path to system manifest (default: manifests/SYSTEM_MANIFEST.yaml)",
    )
    check_parser.set_defaults(func=cmd_check)

    ui_parser = subparsers.add_parser("ui", help="Start the local browser workspace")
    ui_parser.add_argument("--manifest", default="manifests/SYSTEM_MANIFEST.yaml", help="Path to system manifest")
    ui_parser.add_argument("--port", type=int, default=8765, help="Loopback port (default: 8765)")
    ui_parser.add_argument("--workspace-root", help="Trusted workspace root (default: inferred from the LAEW repository layout or LAEW_WORKSPACE_ROOT)")
    ui_parser.add_argument("--projects-root", help="Override the Projects directory under the workspace root")
    ui_parser.add_argument("--no-browser", action="store_true", help="Do not open a browser automatically")
    ui_parser.set_defaults(func=cmd_ui)

    # Parse arguments
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    if args.command == "ui":
        from laew.backup.fence import FenceBusyError, FenceConfigurationError
        from laew.backup.writer import enroll_writer_process
        try:
            enroll_writer_process()
        except (FenceBusyError, FenceConfigurationError, OSError):
            print("[FAIL] Installation maintenance fence is unavailable.", file=sys.stderr)
            return 1
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

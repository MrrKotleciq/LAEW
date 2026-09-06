"""LAEW CLI - Command-line interface for Local AI Engineering Workspace."""

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

from laew.manifest import load_manifest, ManifestError
from laew.tools import (
    FilesystemTool,
    GitTool,
    TerminalTool,
    WebTool,
    configure_tool_logger,
)
from laew.security.path_resolver import PathResolver


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


def cmd_tool(args) -> int:
    """
    Execute a tool operation with security enforcement.

    Returns:
        0 if operation succeeded, 1 if failed
    """
    tool_name = args.tool
    operation = args.operation

    # Parse tool arguments
    tool_args = {}
    if args.args:
        for arg in args.args:
            if "=" in arg:
                key, value = arg.split("=", 1)
                tool_args[key] = value
            else:
                print(f"[FAIL] Invalid argument format: {arg} (expected key=value)")
                return 1

    # Configure logging if requested
    log_file_handle = None
    if args.log:
        log_file_handle = open(args.log, "a", encoding="utf-8")
        configure_tool_logger(output=log_file_handle)

    try:
        # Instantiate appropriate tool
        tools_map = {
            "filesystem": FilesystemTool,
            "git": GitTool,
            "terminal": TerminalTool,
            "web": WebTool,
        }

        if tool_name not in tools_map:
            print(f"[FAIL] Unknown tool: {tool_name}")
            print(f"  Available tools: {', '.join(tools_map.keys())}")
            return 1

        # Instantiate tool (different constructors for different tools)
        if tool_name == "filesystem":
            tool = FilesystemTool()
        elif tool_name == "git":
            tool = GitTool()
        elif tool_name == "terminal":
            tool = TerminalTool()
        elif tool_name == "web":
            tool = WebTool()

        # Auto-approve if not requiring approval
        if not args.require_approval:
            tool.approve()

        # Execute operation
        print(f"Executing: {tool_name}.{operation}")
        if tool_args:
            print(f"Arguments: {tool_args}")

        result = tool.call(operation, **tool_args)

        # Output result
        if result.success:
            print("[OK] Operation succeeded")
            if result.data:
                if isinstance(result.data, str):
                    print(result.data)
                else:
                    print(json.dumps(result.data, indent=2))
            return 0
        else:
            print(f"[FAIL] Operation failed: {result.error_code}")
            if result.error_message:
                print(f"  {result.error_message}")
            return 1
    finally:
        if log_file_handle:
            # Reset logger output and close handle
            configure_tool_logger(output=None)
            log_file_handle.close()


def main() -> int:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="laew",
        description="Local AI Engineering Workspace CLI",
    )

    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 0.1.0",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # check command
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

    # tool command
    tool_parser = subparsers.add_parser(
        "tool",
        help="Execute a tool operation",
    )
    tool_parser.add_argument(
        "tool",
        choices=["filesystem", "git", "terminal", "web"],
        help="Tool to execute",
    )
    tool_parser.add_argument(
        "operation",
        help="Operation to perform",
    )
    tool_parser.add_argument(
        "args",
        nargs="*",
        help="Operation arguments in key=value format",
    )
    tool_parser.add_argument(
        "--require-approval",
        action="store_true",
        help="Require user approval for mutations",
    )
    tool_parser.add_argument(
        "--log",
        help="Log file for tool invocations",
    )
    tool_parser.set_defaults(func=cmd_tool)

    # Parse arguments
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

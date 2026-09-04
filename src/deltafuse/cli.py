# Command Line Interface for DeltaFuse Framework.

from __future__ import annotations
import argparse
import sys
from pathlib import Path
from deltafuse.core.installer import install, InstallationError
from deltafuse.core.fsm import validate_change_package, check_gate


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="deltafuse", description="DeltaFuse Specification-Driven AI Engineering Tool")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # init command
    init_parser = subparsers.add_parser("init", help="Initialize DeltaFuse product layout")
    init_parser.add_argument("target", nargs="?", default=".", help="Target product directory (default: current dir)")
    init_parser.add_argument("--force", "-f", action="store_true", help="Force upgrade/overwrite existing lock")

    # validate command
    val_parser = subparsers.add_parser("validate", help="Validate Change package structural invariants")
    val_parser.add_argument("change_path", nargs="?", default=".", help="Path to Change package directory")

    # check-gate command
    gate_parser = subparsers.add_parser("check-gate", help="Check lifecycle gate preconditions")
    gate_parser.add_argument("change_path", help="Path to Change package directory")
    gate_parser.add_argument("--gate", "-g", required=True, help="Target gate (intake, analyzed, specified, decomposed, targeting, implemented, converged)")

    args = parser.parse_args(argv)

    if args.command == "init":
        try:
            result = install(target_dir=args.target, force=args.force)
            print(f"DeltaFuse {result.version} successfully installed into {result.target_dir}")
            print(f"Content hash: sha256:{result.content_hash}")
            return 0
        except InstallationError as e:
            print(f"Installation Error: {e}", file=sys.stderr)
            return 1
        except Exception as e:
            print(f"Unexpected error during installation: {e}", file=sys.stderr)
            return 2

    elif args.command == "validate":
        target = Path(args.change_path)
        errors = validate_change_package(target)
        if errors:
            print(f"Validation failed for {target} with {len(errors)} error(s):", file=sys.stderr)
            for err in errors:
                print(f"  - {err}", file=sys.stderr)
            return 1
        print(f"Change package {target} is valid.")
        return 0

    elif args.command == "check-gate":
        target = Path(args.change_path)
        errors = check_gate(target, args.gate)
        if errors:
            print(f"Gate {args.gate} check failed for {target}:", file=sys.stderr)
            for err in errors:
                print(f"  - {err}", file=sys.stderr)
            return 1
        print(f"Gate {args.gate} passed for {target}.")
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())

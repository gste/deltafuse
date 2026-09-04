"""Command Line Interface for DeltaFuse Framework."""

from __future__ import annotations
import argparse
import sys
from pathlib import Path
from deltafuse.core.installer import install, InstallationError


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="deltafuse", description="DeltaFuse Specification-Driven AI Engineering Tool")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # init command
    init_parser = subparsers.add_parser("init", help="Initialize DeltaFuse product layout")
    init_parser.add_argument("target", nargs="?", default=".", help="Target product directory (default: current dir)")
    init_parser.add_argument("--force", "-f", action="store_true", help="Force upgrade/overwrite existing lock")

    # validate command (placeholder for Stage 3)
    val_parser = subparsers.add_parser("validate", help="Validate Change package or specification")
    val_parser.add_argument("--change", "-c", help="Target change ID (e.g. CHG-001)")

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

    return 0


if __name__ == "__main__":
    sys.exit(main())

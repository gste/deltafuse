# Command Line Interface for DeltaFuse Framework.

from __future__ import annotations
import argparse
import sys
from pathlib import Path
from deltafuse.core.installer import install, InstallationError
from deltafuse.core.fsm import validate_change_package, check_gate, find_repo_root
from deltafuse.core.archiver import archive_change, ArchivalError
from deltafuse.core.evidence import EvidenceRunError, run_evidence
from deltafuse.core.layout import validate_product_layout
from deltafuse.core.context import validate_context_budget, validate_task_context_budget
from deltafuse.core.frontmatter import parse_frontmatter
from deltafuse.evals.dataset import EvalDataset
from deltafuse.evals.providers import MockLLMProvider, RealLLMProvider
from deltafuse.evals.reporter import export_report
from deltafuse.evals.runner import run_eval


def main(argv: list[str] | None = None) -> int:
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    parser = argparse.ArgumentParser(prog="deltafuse", description="DeltaFuse Specification-Driven AI Engineering Tool")
    subparsers = parser.add_subparsers(dest="command", required=True)

    raw = list(sys.argv[1:] if argv is None else argv)
    evidence_argv: list[str] = []
    if raw and raw[0] == "evidence" and "--" in raw:
        cut = raw.index("--")
        evidence_argv = raw[cut + 1 :]
        raw = raw[:cut]

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

    # archive command
    arch_parser = subparsers.add_parser("archive", help="Archive a converged Change package")
    arch_parser.add_argument("change_path", help="Path to Change package directory")
    arch_parser.add_argument("--force", "-f", action="store_true", help="Force archive without converged check")

    # validate-layout command (P6.1)
    layout_parser = subparsers.add_parser("validate-layout", help="Validate product repository layout, locks, and adapters")
    layout_parser.add_argument("product_path", nargs="?", default=".", help="Path to product repository root (default: current dir)")

    # evidence command (WK-002)
    ev_parser = subparsers.add_parser(
        "evidence",
        help="Run a command after '--' and write evidence/red|green|regression YAML",
    )
    ev_parser.add_argument("change_path", help="Path to Change package directory")
    ev_parser.add_argument(
        "--phase",
        "-p",
        required=True,
        choices=["red", "green", "regression"],
        help="Evidence phase to record",
    )
    ev_parser.add_argument("--task", "-t", required=True, help="Task id (TASK-NNN)")
    ev_parser.add_argument(
        "--changed-path",
        action="append",
        default=[],
        dest="changed_paths",
        help="Relative path written by the worker (repeatable)",
    )
    ev_parser.add_argument("--timeout", type=int, default=90, help="Command timeout in seconds")

    # lint-context command (P7.6)
    ctx_parser = subparsers.add_parser("lint-context", help="Lint Change package context budget and contracts")
    ctx_parser.add_argument("change_path", nargs="?", default=".", help="Path to Change package directory")

    # eval command (Stage 5)
    eval_parser = subparsers.add_parser("eval", help="Run LLM Eval benchmark against DeltaFuse dataset and gatekeepers")
    eval_parser.add_argument("--dataset", "-d", default=None, help="Path to custom eval dataset YAML/JSON file")
    eval_parser.add_argument("--provider", "-p", default="mock", choices=["mock", "real"], help="LLM Provider to use (mock or real)")
    eval_parser.add_argument("--scenario", "-s", default="golden",  choices=["golden", "schema_violation", "fsm_violation", "routing_mismatch", "claim_hallucination"], help="Mock LLM simulation scenario")
    eval_parser.add_argument("--output", "-o", default="text", choices=["text", "json", "markdown"], help="Output format for report")
    eval_parser.add_argument("--out-file", default=None, help="File path to save the eval report")
    eval_parser.add_argument("--min-schema-compliance", type=float, default=0.0, help="Minimum required Schema Compliance Rate (0.0 - 100.0)")
    eval_parser.add_argument("--min-gate-pass-rate", type=float, default=0.0, help="Minimum required Gate Pass Rate (0.0 - 100.0)")

    args = parser.parse_args(raw)

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

    elif args.command == "archive":
        target = Path(args.change_path)
        try:
            dest = archive_change(target, force=args.force)
            print(f"Change package {target.name} successfully archived to {dest}")
            return 0
        except ArchivalError as ae:
            print(f"Archival failed: {ae}", file=sys.stderr)
            return 1
        except Exception as ex:
            print(f"Unexpected error during archival: {ex}", file=sys.stderr)
            return 2

    elif args.command == "validate-layout":
        target = Path(args.product_path)
        errors = validate_product_layout(target)
        if errors:
            print(f"Product layout validation failed for {target} with {len(errors)} error(s):", file=sys.stderr)
            for err in errors:
                print(f"  - {err}", file=sys.stderr)
            return 1
        print(f"DeltaFuse product layout at {target} is valid.")
        return 0

    elif args.command == "evidence":
        try:
            outcome = run_evidence(
                Path(args.change_path),
                phase=args.phase,
                task=args.task,
                argv=evidence_argv,
                changed_paths=args.changed_paths,
                timeout=args.timeout,
            )
        except EvidenceRunError as ex:
            print(f"Evidence run failed: {ex}", file=sys.stderr)
            return 2
        print(f"Wrote {outcome.dest}")
        if outcome.authentic:
            print("Evidence is authentic.")
            return 0
        print("Evidence is not authentic:", file=sys.stderr)
        for err in outcome.errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    elif args.command == "lint-context":
        target = Path(args.change_path)
        repo_root = find_repo_root(target)
        slices_dir = target / "slices"
        errors: list[str] = []
        if slices_dir.is_dir():
            for sf in slices_dir.glob("*.md"):
                try:
                    meta, _ = parse_frontmatter(sf.read_text(encoding="utf-8"))
                    budget = meta.get("context_budget")
                    if budget and isinstance(budget, dict):
                        ref_files: list[Path] = []
                        for sref in meta.get("spec_refs", []):
                            sp_rel = sref.split("#")[0]
                            ref_files.append(repo_root / sp_rel)
                        b_errs = validate_context_budget(
                            budget, ref_files, repo_root=repo_root
                        )
                        errors.extend(f"{sf.name}: {e}" for e in b_errs)
                except Exception as ex:
                    errors.append(f"{sf.name}: {ex}")
        tasks_dir = target / "tasks"
        if tasks_dir.is_dir():
            for tf in tasks_dir.glob("*.md"):
                try:
                    meta, _ = parse_frontmatter(tf.read_text(encoding="utf-8"))
                    budget = meta.get("context_budget")
                    if budget and isinstance(budget, dict):
                        b_errs = validate_task_context_budget(
                            budget,
                            meta.get("spec_refs") or [],
                            meta.get("allowed_paths") or [],
                            repo_root,
                        )
                        errors.extend(f"{tf.name}: {e}" for e in b_errs)
                    else:
                        errors.append(
                            f"{tf.name}: context_budget is required "
                            "(max_tokens/max_files) for Declare and Implement"
                        )
                except Exception as ex:
                    errors.append(f"{tf.name}: {ex}")
        if errors:
            print(f"Context budget validation failed for {target} with {len(errors)} error(s):", file=sys.stderr)
            for err in errors:
                print(f"  - {err}", file=sys.stderr)
            return 1
        print(f"Context budget for {target} is within limits.")
        return 0

    elif args.command == "eval":
        try:
            if args.dataset:
                dataset = EvalDataset.load_from_file(args.dataset)
            else:
                dataset = EvalDataset.get_default_dataset()

            if args.provider == "real":
                provider = RealLLMProvider()
            else:
                provider = MockLLMProvider(scenario=args.scenario)
            report = run_eval(dataset=dataset, provider=provider)

            output_text = export_report(report, format_type=args.output, output_file=args.out_file)
            print(output_text)

            failed_threshold = False
            if report.schema_compliance_rate < args.min_schema_compliance:
                print(
                    f"Error: Schema Compliance Rate {report.schema_compliance_rate:.1f}% is below required {args.min_schema_compliance:.1f}%",
                    file=sys.stderr,
                )
                failed_threshold = True

            if report.gate_pass_rate < args.min_gate_pass_rate:
                print(
                    f"Error: Gate Pass Rate {report.gate_pass_rate:.1f}% is below required {args.min_gate_pass_rate:.1f}%",
                    file=sys.stderr,
                )
                failed_threshold = True

            if failed_threshold:
                return 1

            return 0 if report.failed_cases == 0 else 1
        except Exception as ex:
            print(f"Evaluation failed with error: {ex}", file=sys.stderr)
            return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())

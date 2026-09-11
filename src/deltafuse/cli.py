# Command Line Interface for DeltaFuse Framework.

from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
from deltafuse.core.installer import install, InstallationError
from deltafuse.core.fsm import validate_change_package, check_gate, find_repo_root
from deltafuse.core.archiver import archive_change, ArchivalError
from deltafuse.core.evidence import EvidenceRunError, run_evidence
from deltafuse.core.layout import validate_product_layout
from deltafuse.core.board import BoardError, build_board_snapshot
from deltafuse.core.analyze import CoverageError, write_coverage
from deltafuse.core.queue import (
    QueueError,
    build_work_queue,
    format_human_blocked_queue,
    format_human_guide,
    format_item,
    format_queue,
    load_product_root,
    queue_snapshot,
    select_next,
)
from deltafuse.core.decide import DecideError, apply_decision
from deltafuse.core.steps import step_names
from deltafuse.core.context import validate_context_budget, validate_task_context_budget
from deltafuse.core.frontmatter import parse_frontmatter
from deltafuse.bench.loader import PACK_ENV as BENCH_PACK_ENV, STAGES as BENCH_STAGES


def _journal(start: Path | str, **event: object) -> None:
    from deltafuse.bench.journal import record_event

    record_event(start, **event)


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
        help="Relative path written by the Worker (repeatable)",
    )
    ev_parser.add_argument("--timeout", type=int, default=90, help="Command timeout in seconds")

    cov_parser = subparsers.add_parser(
        "coverage",
        help="Write coverage.yaml from routing and slices (no LLM)",
    )
    cov_parser.add_argument("change_path", help="Path to Change package directory")

    # next / work queue (WK-003)
    next_parser = subparsers.add_parser(
        "next",
        help="Select the next ready lifecycle step (no LLM)",
    )
    next_parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Product root or Change package directory (default: current dir)",
    )
    next_parser.add_argument("--list", action="store_true", help="Print the full ready/blocked queue")
    next_parser.add_argument("--json", action="store_true", help="Write a JSON snapshot to stdout")
    next_parser.add_argument(
        "--human",
        action="store_true",
        help="Print a checklist from the step contract (same files, not a second process)",
    )
    next_parser.add_argument(
        "--step",
        choices=list(step_names()),
        help="Only select this step",
    )

    decide_parser = subparsers.add_parser(
        "decide",
        help="Apply a Human Gate choice after the human answers (no LLM, no auto-accept)",
    )
    decide_parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Product root, or Change directory for --spec",
    )
    decide_parser.add_argument(
        "--decision",
        "-d",
        default=None,
        help="DEC id or docs/decisions/*.md path",
    )
    decide_parser.add_argument(
        "--spec",
        action="store_true",
        help="Apply the specification Human Gate (spec-delta.md on the Change path)",
    )
    decide_parser.add_argument(
        "--status",
        required=True,
        choices=["accepted", "rejected"],
        help="Recorded human choice",
    )
    decide_parser.add_argument("--json", action="store_true", help="Write JSON to stdout")

    # board snapshot (FM-001)
    board_parser = subparsers.add_parser(
        "board",
        help="Emit a read-only fuse-map board snapshot (no product writes)",
    )
    board_parser.add_argument(
        "product_path",
        nargs="?",
        default=".",
        help="Product repository root (default: current dir)",
    )
    board_parser.add_argument(
        "--json",
        action="store_true",
        default=True,
        help="Write the snapshot JSON to stdout (default; the only stdout on success)",
    )
    board_parser.add_argument(
        "--archive",
        action="store_true",
        help="Include archived Change cards",
    )

    # lint-context command (P7.6)
    ctx_parser = subparsers.add_parser("lint-context", help="Lint Change package context budget and contracts")
    ctx_parser.add_argument("change_path", nargs="?", default=".", help="Path to Change package directory")

    bench_parser = subparsers.add_parser(
        "bench",
        help="Agent-agnostic Worker bench: init a case, score the disk, compare runs (no LLM)",
    )
    bench_sub = bench_parser.add_subparsers(dest="bench_cmd", required=True)
    bench_init = bench_sub.add_parser("init", help="Install a product workspace for a bench case")
    bench_init.add_argument("case_id", help="Case id (M01-cooldown floor, M02-policy-stats frontier)")
    bench_init.add_argument("product_dir", help="New worker sandbox (must be empty unless --force)")
    bench_init.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Recreate the sandbox if the directory already exists",
    )
    bench_init.add_argument(
        "--pack",
        default=None,
        help="Judge pack (framework root, process/bench, or cases/). Default: this checkout",
    )
    bench_score = bench_sub.add_parser("score", help="Judge: score a sandbox from the pack (not for the Worker)")
    bench_score.add_argument("product_dir", help="Product root created by bench init")
    bench_score.add_argument("--stage", choices=list(BENCH_STAGES), help="Score one lifecycle step")
    bench_score.add_argument("--json", action="store_true", help="Write the scorecard as JSON")
    bench_score.add_argument("--label", default=None, help="Run label (agent+model) stored in the JSON")
    bench_score.add_argument("--out-file", default=None, help="Save JSON outside the sandbox")
    bench_score.add_argument(
        "--pack",
        default=None,
        help=f"Judge pack required unless {BENCH_PACK_ENV} is set",
    )
    bench_score.add_argument(
        "--verbose",
        action="store_true",
        help="Include hidden-suite pytest output (judge-only; do not share with the Worker)",
    )
    bench_cmp = bench_sub.add_parser("compare", help="Compare two bench score JSON files")
    bench_cmp.add_argument("left", help="First score JSON")
    bench_cmp.add_argument("right", help="Second score JSON")
    bench_journal = bench_sub.add_parser(
        "journal",
        help="Judge: collect Core attempts from a sandbox journal (no LLM)",
    )
    bench_journal.add_argument("product_dir", help="Product root created by bench init")

    args = parser.parse_args(raw)

    if args.command == "init":
        try:
            result = install(target_dir=args.target, force=args.force)
            print(f"DeltaFuse {result.version} successfully installed into {result.target_dir}")
            print(f"Content hash: sha256:{result.content_hash}")
            if result.adapter_mode == "link":
                print("Adapter skills are relative links into the nested framework checkout.")
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
        _journal(target, cmd="validate", ok=not errors, errors=errors, n_errors=len(errors))
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
        _journal(
            target,
            cmd="check-gate",
            gate=args.gate,
            ok=not errors,
            errors=errors,
            n_errors=len(errors),
        )
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
            _journal(target, cmd="archive", ok=True)
            print(f"Change package {target.name} successfully archived to {dest}")
            return 0
        except ArchivalError as ae:
            _journal(target, cmd="archive", ok=False, errors=[str(ae)])
            print(f"Archival failed: {ae}", file=sys.stderr)
            return 1
        except Exception as ex:
            _journal(target, cmd="archive", ok=False, errors=[str(ex)])
            print(f"Unexpected error during archival: {ex}", file=sys.stderr)
            return 2

    elif args.command == "validate-layout":
        target = Path(args.product_path)
        errors = validate_product_layout(target)
        _journal(target, cmd="validate-layout", ok=not errors, errors=errors, n_errors=len(errors))
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
            _journal(
                Path(args.change_path),
                cmd="evidence",
                phase=args.phase,
                task=args.task,
                ok=False,
                errors=[str(ex)],
            )
            print(f"Evidence run failed: {ex}", file=sys.stderr)
            return 2
        _journal(
            Path(args.change_path),
            cmd="evidence",
            phase=args.phase,
            task=args.task,
            ok=bool(outcome.authentic),
            errors=list(outcome.errors or []),
            n_errors=len(outcome.errors or []),
        )
        print(f"Wrote {outcome.dest}")
        if outcome.authentic:
            print("Evidence is authentic.")
            return 0
        print("Evidence is not authentic:", file=sys.stderr)
        for err in outcome.errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    elif args.command == "coverage":
        try:
            dest = write_coverage(Path(args.change_path))
        except CoverageError as ex:
            _journal(Path(args.change_path), cmd="coverage", ok=False, errors=[str(ex)])
            print(f"Coverage failed: {ex}", file=sys.stderr)
            return 1
        except Exception as ex:
            _journal(Path(args.change_path), cmd="coverage", ok=False, errors=[str(ex)])
            print(f"Coverage failed: {ex}", file=sys.stderr)
            return 2
        _journal(Path(args.change_path), cmd="coverage", ok=True)
        print(f"Wrote {dest}")
        return 0

    elif args.command == "next":
        target = Path(args.path)
        mode = "list" if args.list else "json" if args.json else "human" if args.human else "select"
        try:
            only = target.resolve() if (target.resolve() / "change.yaml").is_file() else None
            queue = build_work_queue(target, only_change=only)
        except QueueError as ex:
            _journal(target, cmd="next", ok=False, mode=mode, errors=[str(ex)])
            print(f"Next failed: {ex}", file=sys.stderr)
            return 2
        selected = select_next(queue, step=args.step)
        _journal(
            target if only is None else only,
            cmd="next",
            ok=True if mode in {"list", "json"} else selected is not None,
            mode=mode,
            skill=selected.skill if selected is not None else None,
            step=selected.step if selected is not None else None,
            change=selected.change_id if selected is not None else None,
            empty=selected is None,
        )
        guide = (
            format_human_guide(selected)
            if selected is not None
            else format_human_blocked_queue(queue)
        )
        if args.json:
            payload = queue_snapshot(
                queue,
                selected=selected,
                product_root=load_product_root(target if only is None else only),
            )
            if args.human:
                payload["guide"] = guide
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        elif args.human:
            if selected is not None:
                print(guide)
            else:
                print(guide, file=sys.stderr)
        elif args.list:
            print(format_queue(queue))
        elif selected is not None:
            print(format_item(selected))
        else:
            print("No ready work.", file=sys.stderr)
            print(format_queue(queue), file=sys.stderr)
            print("To start a new Change: /intake", file=sys.stderr)
        return 0 if selected is not None else 1

    elif args.command == "decide":
        target = Path(args.path)
        try:
            result = apply_decision(
                target,
                status=args.status,
                decision=args.decision,
                spec=args.spec,
            )
        except DecideError as ex:
            _journal(target, cmd="decide", ok=False, errors=[str(ex)])
            print(f"Decide failed: {ex}", file=sys.stderr)
            return 1
        except QueueError as ex:
            _journal(target, cmd="decide", ok=False, errors=[str(ex)])
            print(f"Decide failed: {ex}", file=sys.stderr)
            return 2
        _journal(
            target,
            cmd="decide",
            ok=True,
            gate=result.get("gate"),
            status=result.get("status"),
            decision=result.get("decision"),
        )
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(f"decide: {result.get('gate')} {result.get('status')}")
            if result.get("decision"):
                print(f"decision: {result['decision']}")
            if result.get("change_status"):
                print(f"change_status: {result['change_status']}")
            for rel in result.get("written") or []:
                print(f"wrote: {rel}")
            for err in result.get("gate_errors") or []:
                print(f"gate: {err}", file=sys.stderr)
        return 0

    elif args.command == "board":
        target = Path(args.product_path)
        try:
            snapshot = build_board_snapshot(
                target,
                include_archive=args.archive,
            )
        except BoardError as ex:
            _journal(target, cmd="board", ok=False, errors=[str(ex)])
            print(f"Board failed: {ex}", file=sys.stderr)
            return 2
        _journal(target, cmd="board", ok=True)
        print(json.dumps(snapshot, ensure_ascii=False, indent=2))
        return 0

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
        _journal(target, cmd="lint-context", ok=not errors, errors=errors, n_errors=len(errors))
        if errors:
            print(f"Context budget validation failed for {target} with {len(errors)} error(s):", file=sys.stderr)
            for err in errors:
                print(f"  - {err}", file=sys.stderr)
            return 1
        print(f"Context budget for {target} is within limits.")
        return 0

    elif args.command == "bench":
        from deltafuse.bench import BenchError
        from deltafuse.bench.init_product import format_worker_start_prompt, init_bench_product
        from deltafuse.bench.score import compare_reports, format_score, score_product

        try:
            if args.bench_cmd == "init":
                meta = init_bench_product(
                    args.case_id,
                    args.product_dir,
                    pack_root=args.pack,
                    force=args.force,
                )
                product = Path(args.product_dir).resolve()
                print(f"Bench {meta['case']} ready in {product}")
                print("Open that directory as the Worker workspace, then paste:")
                print()
                print("----- paste into the Worker -----")
                print(format_worker_start_prompt(meta))
                print("----- end -----")
                return 0
            if args.bench_cmd == "score":
                from deltafuse.bench.loader import assert_scorecard_outside_sandbox

                product = Path(args.product_dir)
                if args.out_file:
                    assert_scorecard_outside_sandbox(args.out_file, product)
                report = score_product(
                    args.product_dir,
                    stage=args.stage,
                    label=args.label,
                    pack_root=args.pack,
                    reveal_hidden=args.verbose,
                )
                payload = json.dumps(report, ensure_ascii=False, indent=2)
                if args.out_file:
                    Path(args.out_file).write_text(payload + "\n", encoding="utf-8")
                if args.json:
                    print(payload)
                else:
                    print(format_score(report))
                return 0 if report.get("pass") else 1
            if args.bench_cmd == "journal":
                from deltafuse.bench.journal import collect_attempts, load_events

                payload = collect_attempts(load_events(Path(args.product_dir).resolve()))
                print(json.dumps(payload, ensure_ascii=False, indent=2))
                return 0
            left = json.loads(Path(args.left).read_text(encoding="utf-8"))
            right = json.loads(Path(args.right).read_text(encoding="utf-8"))
            print(compare_reports(left, right))
            return 0
        except BenchError as ex:
            print(f"Bench failed: {ex}", file=sys.stderr)
            return 2
        except Exception as ex:
            print(f"Bench failed: {ex}", file=sys.stderr)
            return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())

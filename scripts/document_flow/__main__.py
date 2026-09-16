"""DeltaFuse J03 benchmark CLI entrypoint."""

import sys
import argparse
from pathlib import Path

from scripts.document_flow.runner import execute_benchmark_run


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="DeltaFuse J03 Document Flow Benchmark Runner")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_p = subparsers.add_parser("run", help="Execute a benchmark run")
    run_p.add_argument("--run-id", required=True, help="Unique run ID")
    run_p.add_argument("--out", required=True, help="Output directory for evidence store")
    run_p.add_argument("--sandbox", required=True, help="Sandbox workspace directory")
    run_p.add_argument("--profile-id", default="default-profile", help="Worker profile ID")
    run_p.add_argument("--preflight-only", action="store_true", help="Run preflight checks only")

    cal_p = subparsers.add_parser("calibrate", help="Run mutation calibration and freeze judge pack")
    cal_p.add_argument("--plan", default="process/bench/cases/J03-document-flow/mutations/manifest.json", help="Path to mutations manifest")
    cal_p.add_argument("--out", default="process/bench/cases/J03-document-flow/reports", help="Output directory for calibration report")

    sup_p = subparsers.add_parser("supervise", help="Supervise product sandbox through DeltaFuse lifecycle")
    sup_p.add_argument("sandbox", help="Path to product sandbox directory")
    sup_p.add_argument("--step-once", action="store_true", help="Execute single supervisor step")
    sup_p.add_argument("--little-coder", action="store_true", help="Drive local little-coder worker")
    sup_p.add_argument("--model", default="poolside/laguna-xs-2.1", help="Worker model ID")
    sup_p.add_argument("--max-iterations", type=int, default=50, help="Maximum supervisor iterations")

    args = parser.parse_args(argv)

    if args.command == "supervise":
        from scripts.document_flow.supervisor import BenchmarkSupervisor
        supervisor = BenchmarkSupervisor(
            args.sandbox,
            use_little_coder=args.little_coder,
            model=args.model,
            max_iterations=args.max_iterations,
        )
        if args.step_once:
            res, _ = supervisor.step()
            print(f"Step outcome: step={res.step}, status={res.status}, action={res.action_taken}")
            return 0 if res.status in ("advanced", "gate_accepted", "converged") else 1
        outcomes = supervisor.run_until_complete()
        final = outcomes[-1] if outcomes else None
        return 0 if final and final.status == "converged" else 1

    if args.command == "run":
        outcome = execute_benchmark_run(
            run_id=args.run_id,
            output_dir=args.out,
            sandbox_dir=args.sandbox,
            profile_id=args.profile_id,
            preflight_only=args.preflight_only,
        )
        print(f"Run finished: status={outcome.status}, score={outcome.score}, verdict={outcome.verdict}")
        return 0 if outcome.status in ("passed", "preflight_passed") else 1

    if args.command == "calibrate":
        from scripts.document_flow.calibrate import run_calibration
        summary = run_calibration(manifest_path=args.plan, out_dir=args.out)
        print(f"Calibration finished: acceptable={summary.acceptable}, killed={summary.killed_count}/{summary.total_candidates} ({summary.kill_rate*100:.1f}%)")
        return 0 if summary.acceptable else 1

    return 1


if __name__ == "__main__":
    sys.exit(main())

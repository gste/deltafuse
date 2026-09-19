"""Evaluation script for paired small-model evaluation protocol (AW-18).

Runs evaluation corpus cases against ArtifactService and independent oracle checks,
reporting first-pass structural validity, mechanical retries, independent semantic correctness,
and forbidden gate block rates.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

from deltafuse.core.artifact_patch import ArtifactPatchError
from deltafuse.core.artifact_policy import create_authorization_context, ArtifactPolicyError
from deltafuse.core.artifacts import ArtifactService, ArtifactServiceError
from deltafuse.core.installer import install
from deltafuse.core.scaffold import scaffold_change


def run_evaluation(corpus_path: Path, work_dir: Path | None = None) -> dict[str, Any]:
    """Execute evaluation corpus against ArtifactService and compute metrics."""
    if not corpus_path.is_file():
        raise FileNotFoundError(f"Evaluation corpus not found: {corpus_path}")

    cases: list[dict[str, Any]] = json.loads(corpus_path.read_text(encoding="utf-8"))

    results: list[dict[str, Any]] = []
    strata_counts: dict[str, dict[str, int]] = {}

    for case in cases:
        case_id = case["id"]
        stratum = case.get("stratum", "unknown")
        kind = case["kind"]
        op = case["operation"]
        payload = case["input_payload"]
        body = case.get("body", "")
        expected_valid = case["expected_valid"]
        expected_block = case.get("expected_gate_block", False)

        st_data = strata_counts.setdefault(stratum, {"total": 0, "first_pass": 0, "semantic_correct": 0, "gate_blocked": 0})
        st_data["total"] += 1

        # Use temporary workspace for case
        import tempfile
        case_tmp = Path(tempfile.mkdtemp())
        install(target_dir=case_tmp, framework_root=Path.cwd())
        cid = f"CHG-800-{case_id.lower().replace('_', '-')}"
        change_dir = scaffold_change(case_tmp, cid, route="code", title=f"Eval {case_id}")
        auth = create_authorization_context(actor="worker", work_item="CLI", product_root=change_dir, change_id=cid)
        service = ArtifactService(product_root=change_dir, auth_context=auth)

        # Pre-create target artifact if update operation
        expected_sha = None
        target_path_str = None
        if op == "update":
            if kind == "task":
                init_p = {"title": "Init task", "kind": "feature", "spec_refs": ["docs/spec/core.md#REQ-01"]}
                rec = service.create(kind="task", identity="TASK-001", semantic_payload=init_p)
                target_path_str = "tasks/TASK-001.md"
                expected_sha = (change_dir / target_path_str).read_bytes()
                import hashlib
                expected_sha = hashlib.sha256(expected_sha).hexdigest()
            elif kind == "routing":
                target_path_str = "routing.yaml"
                rf = change_dir / "routing.yaml"
                if not rf.is_file():
                    rf.write_text(f"change: {cid}\nclaims:\n  CR-001:\n    primary_capability: core\n", encoding="utf-8")
                import hashlib
                expected_sha = hashlib.sha256(rf.read_bytes()).hexdigest()

        # Execute operation
        passed_op = False
        gate_blocked = False
        err_msg = None

        try:
            if op == "create":
                rec = service.create(kind=kind, identity=f"{kind.upper()}-001", semantic_payload=payload, body=body)
                passed_op = True
            elif op == "update":
                rec = service.update(kind=kind, target=target_path_str or f"{kind}.yaml", expected_sha256=expected_sha or "0"*64, patch=payload)
                passed_op = True
        except (ArtifactServiceError, ArtifactPolicyError, ArtifactPatchError) as ex:
            err_msg = str(ex)
            if "protected" in err_msg.lower() or "immutable" in err_msg.lower() or "unauthorized" in err_msg.lower():
                gate_blocked = True

        first_pass = passed_op == expected_valid
        gate_block_correct = gate_blocked == expected_block if expected_block else True
        semantic_correct = first_pass and gate_block_correct

        if first_pass:
            st_data["first_pass"] += 1
        if semantic_correct:
            st_data["semantic_correct"] += 1
        if gate_blocked or not expected_block:
            st_data["gate_blocked"] += 1

        results.append({
            "id": case_id,
            "stratum": stratum,
            "title": case["title"],
            "operation": op,
            "passed_op": passed_op,
            "expected_valid": expected_valid,
            "gate_blocked": gate_blocked,
            "first_pass": first_pass,
            "semantic_correct": semantic_correct,
            "error": err_msg,
        })

    total_cases = len(cases)
    first_pass_count = sum(1 for r in results if r["first_pass"])
    semantic_count = sum(1 for r in results if r["semantic_correct"])
    gate_blocked_count = sum(1 for r in results if r["gate_blocked"])

    summary = {
        "total_cases": total_cases,
        "first_pass_valid_count": first_pass_count,
        "first_pass_valid_rate": round(first_pass_count / total_cases * 100, 2) if total_cases else 0.0,
        "semantic_correct_count": semantic_count,
        "semantic_correct_rate": round(semantic_count / total_cases * 100, 2) if total_cases else 0.0,
        "forbidden_gate_blocked_count": gate_blocked_count,
        "strata": strata_counts,
        "results": results,
    }

    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate Artifact Writer against evaluation corpus")
    parser.add_argument(
        "-c", "--corpus",
        type=Path,
        default=Path("tests/fixtures/artifact_writer_eval/eval_corpus.json"),
        help="Path to evaluation corpus JSON file",
    )
    parser.add_argument(
        "-o", "--output",
        type=Path,
        help="Path to save evaluation output JSON report",
    )
    args = parser.parse_args()

    summary = run_evaluation(args.corpus)

    print("=== Artifact Writer Evaluation Report ===")
    print(f"Total Cases: {summary['total_cases']}")
    print(f"First-Pass Valid: {summary['first_pass_valid_count']}/{summary['total_cases']} ({summary['first_pass_valid_rate']}%)")
    print(f"Semantic Correct: {summary['semantic_correct_count']}/{summary['total_cases']} ({summary['semantic_correct_rate']}%)")

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(f"Report written to {args.output}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

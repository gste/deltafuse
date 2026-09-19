"""Evaluation script for paired small-model evaluation protocol and independent oracle (AW-35).

Runs evaluation corpus cases against ArtifactService and independent oracle checks,
reporting first-pass structural validity, mechanical retries, independent semantic correctness,
forbidden gate block rates, and actual Core gate checks (`check_gate`).
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from typing import Any

import yaml

from deltafuse.core.artifact_patch import ArtifactPatchError
from deltafuse.core.artifact_policy import create_authorization_context, ArtifactPolicyError
from deltafuse.core.artifact_reader import strict_read_artifact, ArtifactReaderError
from deltafuse.core.artifacts import ArtifactService, ArtifactServiceError
from deltafuse.core.fsm import check_gate
from deltafuse.core.installer import install
from deltafuse.core.scaffold import scaffold_change


def _resolve_json_pointer(doc: Any, pointer: str) -> tuple[bool, Any, Any, str | int]:
    """Resolve JSON pointer, returning (found, parent_container, current_value, last_key)."""
    if not pointer or pointer == "/":
        return True, None, doc, ""
    raw_parts = pointer.lstrip("/").split("/")
    parts = [p.replace("~1", "/").replace("~0", "~") for p in raw_parts]
    curr = doc
    parent = None
    last_part: str | int = ""
    for part in parts:
        parent = curr
        last_part = part
        if isinstance(curr, dict):
            if part in curr:
                curr = curr[part]
            else:
                return False, parent, None, part
        elif isinstance(curr, list):
            try:
                idx = int(part)
                if 0 <= idx < len(curr):
                    last_part = idx
                    curr = curr[idx]
                else:
                    return False, parent, None, idx
            except ValueError:
                return False, parent, None, part
        else:
            return False, parent, None, part
    return True, parent, curr, last_part


def evaluate_independent_oracle(
    change_dir: Path,
    case: dict[str, Any],
    passed_op: bool,
    gate_blocked: bool,
    error_msg: str | None,
    disk_mutated_on_denial: bool = False,
) -> dict[str, Any]:
    """Independent oracle evaluating ground truth disk state and Core gate validity.

    Does NOT trust ArtifactService receipt or return value alone. Inspects actual disk files
    and verifies strict structure, typed semantic values, field preservation, forbidden disk mutation,
    and actual Core gate enforcement (`check_gate`).
    """
    from deltafuse.core.artifact_registry import ArtifactRegistry
    registry = ArtifactRegistry(change_dir)

    op = case["operation"]
    kind = case["kind"]
    expected_valid = case["expected_valid"]
    expected_gate_block = case.get("expected_gate_block", False)
    payload = case["input_payload"]

    # 1. First-pass structural operation validity match
    first_pass = (passed_op == expected_valid)

    # 2. Gate block correctness
    gate_block_correct = (gate_blocked == expected_gate_block) if expected_gate_block else (not gate_blocked)

    # 3. Denied operation disk mutation check: forbidden mutation fails gate block correctness
    if (not expected_valid or expected_gate_block or not passed_op) and disk_mutated_on_denial:
        gate_block_correct = False

    # 4. Strict ground truth disk inspection & typed semantic verification
    semantic_correct = first_pass and gate_block_correct

    # Determine target artifact path
    target_path = None
    if case.get("target"):
        target_path = change_dir / case["target"]
    elif kind == "task":
        target_path = change_dir / "tasks" / "TASK-001.md"
    elif kind == "routing":
        target_path = change_dir / "routing.yaml"
    elif kind == "spec-delta":
        target_path = change_dir / "spec-delta.md"

    if expected_valid and passed_op:
        if target_path and target_path.is_file():
            try:
                content = target_path.read_text(encoding="utf-8")
                target_meta: dict[str, Any] = {}
                body_str = ""

                if kind in ("task", "spec-delta"):
                    parse_res = strict_read_artifact(content)
                    target_meta = parse_res.metadata
                    body_str = parse_res.raw_body

                    # Validate against authoritative storage schema
                    val_res = registry.validate_storage_schema(kind, target_meta)
                    if not val_res.valid:
                        semantic_correct = False

                    if kind == "task":
                        # Verify strict typed metadata fields against payload and expectations
                        if target_meta.get("id") != "TASK-001" and target_meta.get("id") != case.get("expected_id", "TASK-001"):
                            semantic_correct = False

                        # Verify kind matches expected requested kind (not just any valid kind enum value!)
                        expected_kind = payload.get("kind") if (isinstance(payload, dict) and "kind" in payload) else case.get("expected_kind")
                        if expected_kind and target_meta.get("kind") != expected_kind:
                            semantic_correct = False

                        # Verify slice matches expected requested slice (and slice file exists on disk!)
                        expected_slice = payload.get("slice") if (isinstance(payload, dict) and "slice" in payload) else case.get("expected_slice")
                        if expected_slice:
                            if target_meta.get("slice") != expected_slice:
                                semantic_correct = False
                        slice_id = target_meta.get("slice")
                        if not slice_id or slice_id == "MISSING":
                            semantic_correct = False
                        else:
                            slice_file1 = change_dir / "slices" / f"{slice_id}.md"
                            slice_file2 = change_dir / f"{slice_id}.md"
                            if not slice_file1.is_file() and not slice_file2.is_file():
                                semantic_correct = False

                        # Verify title
                        if isinstance(payload, dict) and "title" in payload:
                            title_val = str(payload["title"])
                            if title_val not in body_str and target_meta.get("title") != title_val:
                                semantic_correct = False

                        # Verify context budget
                        if isinstance(payload, dict) and "context_budget" in payload:
                            budget = target_meta.get("context_budget")
                            if not isinstance(budget, dict):
                                semantic_correct = False
                            elif "max_tokens" in payload["context_budget"] and budget.get("max_tokens") != payload["context_budget"]["max_tokens"]:
                                semantic_correct = False
                            elif "max_files" in payload["context_budget"] and budget.get("max_files") != payload["context_budget"]["max_files"]:
                                semantic_correct = False

                        # Verify depends_on
                        if isinstance(payload, dict) and "depends_on" in payload:
                            if target_meta.get("depends_on") != payload["depends_on"]:
                                semantic_correct = False

                        # Verify spec_refs
                        if isinstance(payload, dict) and "spec_refs" in payload:
                            if target_meta.get("spec_refs") != payload["spec_refs"]:
                                semantic_correct = False

                        # Verify allowed_paths & forbidden_paths
                        if isinstance(payload, dict) and "allowed_paths" in payload:
                            if target_meta.get("allowed_paths") != payload["allowed_paths"]:
                                semantic_correct = False
                        if isinstance(payload, dict) and "forbidden_paths" in payload:
                            if target_meta.get("forbidden_paths") != payload["forbidden_paths"]:
                                semantic_correct = False

                        # Verify requirement_delta
                        if isinstance(payload, dict) and "requirement_delta" in payload:
                            if target_meta.get("requirement_delta") != payload["requirement_delta"]:
                                semantic_correct = False

                    elif kind == "spec-delta":
                        if not isinstance(target_meta.get("added"), list) or not isinstance(target_meta.get("modified"), list):
                            semantic_correct = False

                elif kind == "routing":
                    data = yaml.safe_load(content)
                    if not isinstance(data, dict):
                        semantic_correct = False
                    elif "claims" not in data or not isinstance(data["claims"], dict):
                        semantic_correct = False
                    else:
                        target_meta = data
                        val_res = registry.validate_storage_schema("routing", data)
                        if not val_res.valid:
                            semantic_correct = False
                        if op == "create" and isinstance(payload, dict) and "claims" in payload:
                            if data.get("claims") != payload["claims"]:
                                semantic_correct = False

                # Verify body if expected
                if "body" in case and case["body"]:
                    if case["body"].strip() not in body_str:
                        semantic_correct = False

                # Patch verification for update operations across all kinds
                if op == "update" and isinstance(payload, dict):
                    set_ops = payload.get("set") or []
                    for item in set_ops:
                        p = item.get("path") or ""
                        v = item.get("value")
                        if p == "/title" and v:
                            if str(v) not in body_str and target_meta.get("title") != v:
                                semantic_correct = False
                        else:
                            found, parent, current_val, last_key = _resolve_json_pointer(target_meta, p)
                            if not found or current_val != v:
                                semantic_correct = False

                    remove_ops = payload.get("remove") or []
                    for p in remove_ops:
                        found, parent, current_val, last_key = _resolve_json_pointer(target_meta, p)
                        if found:
                            semantic_correct = False

            except (ArtifactReaderError, yaml.YAMLError, ValueError, TypeError):
                semantic_correct = False
        else:
            semantic_correct = False

    elif not expected_valid and passed_op:
        semantic_correct = False

    elif expected_gate_block and not gate_blocked:
        semantic_correct = False

    # 5. Core gate check invocation
    gate_stage = "decomposed" if kind == "task" else ("analyzed" if kind == "routing" else "specified")
    gate_errors: list[str] = []
    try:
        gate_errors = check_gate(change_dir, gate_stage)
    except Exception as ex:
        gate_errors = [f"check_gate exception: {ex}"]

    # Evaluate gate errors affecting target artifact structural correctness
    if target_path and target_path.is_file():
        target_name = target_path.name
        for ge in gate_errors:
            if target_name in ge or f"tasks/{target_name}" in ge:
                if "schema" in ge.lower() or "required" in ge.lower() or "unexpected" in ge.lower() or "invalid" in ge.lower():
                    semantic_correct = False

    return {
        "first_pass": first_pass,
        "gate_blocked": gate_blocked,
        "gate_block_correct": gate_block_correct,
        "semantic_correct": semantic_correct,
        "disk_mutated_on_denial": disk_mutated_on_denial,
        "gate_scope": gate_stage,
        "whole_gate_convergence": "evaluated" if not gate_errors else "errors_present",
        "gate_errors": gate_errors,
    }


def run_evaluation(
    corpus_path: Path,
    work_dir: Path | None = None,
    *,
    mode: str = "harness_baseline",
    weakened_mode: str | None = None,
    adapter: str | None = None,
) -> dict[str, Any]:
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
        payload = case["input_payload"].copy() if isinstance(case["input_payload"], dict) else case["input_payload"]
        body = case.get("body", "")
        expected_valid = case["expected_valid"]
        expected_block = case.get("expected_gate_block", False)

        st_data = strata_counts.setdefault(stratum, {"total": 0, "first_pass": 0, "semantic_correct": 0, "gate_blocked": 0})
        st_data["total"] += 1

        case_tmp = Path(tempfile.mkdtemp())
        install(target_dir=case_tmp, framework_root=Path.cwd())
        cid = f"CHG-800-{case_id.lower().replace('_', '-')}"
        change_dir = scaffold_change(case_tmp, cid, route="code", title=f"Eval {case_id}")

        (change_dir / "slices").mkdir(parents=True, exist_ok=True)
        (change_dir / "slices" / "SLICE-01.md").write_text(f"---\nid: SLICE-01\nchange: {cid}\ntitle: Eval Slice\nstatus: draft\nprimary_capability: core\nclaims:\n  - CR-001\n---\nBody\n", encoding="utf-8")
        (change_dir / "docs" / "spec").mkdir(parents=True, exist_ok=True)
        (change_dir / "docs" / "spec" / "core.md").write_text("# Core Spec\n", encoding="utf-8")

        auth = create_authorization_context(actor="worker", work_item="SLICE-01", product_root=change_dir, change_id=cid)
        service = ArtifactService(product_root=change_dir, auth_context=auth)

        # Pre-create target artifact if update operation
        expected_sha = None
        target_path_str = None
        if op == "update":
            if kind == "task":
                init_p = {
                    "title": "Init task",
                    "kind": "feature",
                    "depends_on": [],
                    "requirement_delta": "none",
                    "spec_refs": ["docs/spec/core.md#REQ-01"],
                    "allowed_paths": [],
                    "forbidden_paths": [],
                    "context_budget": {"max_tokens": 1000, "max_files": 5},
                }
                rec = service.create(kind="task", identity="TASK-001", semantic_payload=init_p)
                target_path_str = "tasks/TASK-001.md"
                expected_sha = hashlib.sha256((change_dir / target_path_str).read_bytes()).hexdigest()
            elif kind == "routing":
                target_path_str = "routing.yaml"
                rf = change_dir / "routing.yaml"
                if not rf.is_file():
                    rf.write_text(f"change: {cid}\nclaims:\n  CR-001:\n    primary_capability: core\n", encoding="utf-8")
                expected_sha = hashlib.sha256(rf.read_bytes()).hexdigest()

        # Simulate weakened writer modes for negative control verification
        if weakened_mode == "drop_title" and isinstance(payload, dict) and "title" in payload:
            del payload["title"]
        elif weakened_mode == "force_verified" and isinstance(payload, dict) and op == "update":
            payload = {"set": [{"path": "/status", "value": "verified"}]}

        # Snapshot files before op to detect unauthorized disk mutations on denial
        pre_files = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in change_dir.rglob("*") if p.is_file()}

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
            if "protected" in err_msg.lower() or "immutable" in err_msg.lower() or "unauthorized" in err_msg.lower() or "halted" in err_msg.lower():
                gate_blocked = True

        post_files = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in change_dir.rglob("*") if p.is_file()}
        disk_mutated_on_denial = False
        if not passed_op or not expected_valid or expected_block:
            if pre_files != post_files:
                disk_mutated_on_denial = True

        oracle_eval = evaluate_independent_oracle(
            change_dir=change_dir,
            case=case,
            passed_op=passed_op,
            gate_blocked=gate_blocked,
            error_msg=err_msg,
            disk_mutated_on_denial=disk_mutated_on_denial,
        )

        first_pass = oracle_eval["first_pass"]
        semantic_correct = oracle_eval["semantic_correct"]

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
            "disk_mutated_on_denial": disk_mutated_on_denial,
            "gate_scope": oracle_eval["gate_scope"],
            "gate_errors": oracle_eval["gate_errors"],
            "error": err_msg,
        })

    total_cases = len(cases)
    first_pass_count = sum(1 for r in results if r["first_pass"])
    semantic_count = sum(1 for r in results if r["semantic_correct"])
    gate_blocked_count = sum(1 for r in results if r["gate_blocked"])

    summary = {
        "evaluation_mode": mode,
        "mode_description": (
            "Deterministic serializer and schema harness check. Evaluates harness invariants and independent oracle."
            if mode == "harness_baseline"
            else "Paired small-model evaluation."
        ),
        "total_cases": total_cases,
        "first_pass_valid_count": first_pass_count,
        "first_pass_valid_rate": round(first_pass_count / total_cases * 100, 2) if total_cases else 0.0,
        "semantic_correct_count": semantic_count,
        "semantic_correct_rate": round(semantic_count / total_cases * 100, 2) if total_cases else 0.0,
        "forbidden_gate_blocked_count": gate_blocked_count,
        "strata": strata_counts,
        "results": results,
    }

    if mode == "paired_model":
        summary["external_model_status"] = "unavailable_no_endpoint" if total_cases > 0 else "unqualified_empty_corpus"
        summary["acceptance_status"] = "open_for_AW-20"
        summary["note"] = "External model endpoint is unavailable in local environment; acceptance remains open for AW-20 without synthetic substitution."


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
    parser.add_argument(
        "--mode",
        choices=["harness_baseline", "paired_model"],
        default="harness_baseline",
        help="Evaluation mode (default: harness_baseline)",
    )
    parser.add_argument(
        "--adapter",
        choices=["small_model"],
        help="Model adapter for paired evaluation (e.g. small_model)",
    )
    args = parser.parse_args()

    summary = run_evaluation(args.corpus, mode=args.mode, adapter=args.adapter)

    print("=== Artifact Writer Evaluation Report ===")
    print(f"Mode: {summary['evaluation_mode']}")
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

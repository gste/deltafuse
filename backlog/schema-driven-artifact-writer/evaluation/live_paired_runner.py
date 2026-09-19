#!/usr/bin/env python3
"""Live paired small-model evaluation runner for AW-40.

Executes the preregistered paired experiment (evaluation/live-run-2026-09-20/
spec.json) against a real model through the local `little-coder` CLI:

- Arm A (manual raw YAML): the model authors the artifact file content;
  evaluated by strict_read_artifact + authoritative storage schema + the same
  typed semantic assertions the frozen oracle uses. Defense cases must be
  denied (missing-required / invalid-enum / protected-status).
- Arm B (typed Writer): the model produces the semantic payload/patch JSON;
  the runner applies it through ArtifactService exactly like the frozen
  harness and evaluates with the UNCHANGED evaluate_independent_oracle.

Every call is a fresh non-interactive, tool-disabled little-coder invocation.
Raw prompts/outputs/verdicts are appended as JSON trace files; metrics are
computed from traces only (see --summary). Failed/timeout/refused attempts are
retained in denominators.  No output is edited before evaluation (code-fence
stripping only).

Usage:
  python live_paired_runner.py --case CASE-01 --arm B [--attempt-limit 3] [--dry-run]
  python live_paired_runner.py --summary
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "scripts"))

import yaml  # noqa: E402

from deltafuse.core.artifact_patch import ArtifactPatchError  # noqa: E402
from deltafuse.core.artifact_policy import (  # noqa: E402
    create_authorization_context, ArtifactPolicyError,
)
from deltafuse.core.artifact_reader import strict_read_artifact  # noqa: E402
from deltafuse.core.artifacts import ArtifactService, ArtifactServiceError  # noqa: E402
from deltafuse.core.fsm import check_gate  # noqa: E402
from deltafuse.core.installer import install  # noqa: E402
from deltafuse.core.scaffold import scaffold_change  # noqa: E402
from evaluate_artifact_writer import (  # noqa: E402
    evaluate_independent_oracle, _resolve_json_pointer,
)

EVAL_DIR = REPO / "backlog" / "schema-driven-artifact-writer" / "evaluation"
RUN_DIR = EVAL_DIR / "live-run-2026-09-20"
RAW_DIR = RUN_DIR / "raw"
SPEC = json.loads((RUN_DIR / "spec.json").read_text(encoding="utf-8"))
MODEL = SPEC["model"]["model_id"]
LITTLE_CODER = shutil.which("little-coder") or "little-coder"
CORPUS = json.loads(
    (REPO / "tests" / "fixtures" / "artifact_writer_eval" / "eval_corpus.json")
    .read_text(encoding="utf-8")
)
REQUIRED_TASK_FIELDS = [
    "title", "kind", "depends_on", "requirement_delta", "spec_refs",
    "allowed_paths", "forbidden_paths", "context_budget",
]


def call_model(prompt: str, timeout_s: int = 240) -> dict:
    sys_prompt = (
        "You are a precise structured-data authoring assistant. You have no "
        "tools and must never mention or emit tool_calls. You must follow the "
        "user's output-format instruction exactly: output ONLY the requested "
        "structure, with EXACTLY the requested values, and never add extra "
        "fields (no status, changeId, author, created, name, type, "
        "lifecycleStage, metadata or other invented keys)."
    )
    argv = [LITTLE_CODER, "--model", MODEL, "--no-tools", "--no-session",
            "--mode", "text", "--system-prompt", sys_prompt, "-p", prompt]
    started = time.time()
    try:
        proc = subprocess.run(argv, capture_output=True, text=True,
                              encoding="utf-8", errors="replace",
                              timeout=timeout_s)
        ok = proc.returncode == 0
        out = (proc.stdout or "") if ok else ""
        err = (proc.stderr or "")[:2000]
        if not ok:
            out = ""
    except subprocess.TimeoutExpired as exc:
        proc = exc
        ok = False
        out = ""
        err = f"timeout after {timeout_s}s"
    return {
        "argv": [str(a) for a in argv],
        "exit": getattr(proc, "returncode", None),
        "output": out,
        "stderr_tail": err,
        "duration_s": round(time.time() - started, 2),
        "ok": ok,
    }


def extract_json(text: str):
    import re
    if not text:
        return None
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    else:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end > start:
            text = text[start:end + 1]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


HARD_CONSTRAINTS_SHORT = (
    "Output ONLY the requested structure - no prose, no preamble, no closing "
    "remarks, no tool_calls."
)


def intent_text(case: dict) -> str:
    op = case["operation"]
    kind = case["kind"]
    payload = case.get("input_payload")
    lines = [f"{case['title']} (op={op}, kind={kind})."]
    if isinstance(payload, dict):
        lines.append("Requested values (use them exactly): "
                     + json.dumps(payload, ensure_ascii=False))
    if case.get("body"):
        lines.append("Required body text: " + repr(case["body"]))
    return "\n".join(lines)


def arm_a_prompt(case: dict) -> str:
    kind = case["kind"]
    payload = case.get("input_payload") or {}
    lines = [f"Author the file content for a {kind} {case['operation']}:",
             "Requested values (use exactly): "
             + json.dumps(payload, ensure_ascii=False)]
    if case.get("body"):
        lines.append("Body text: " + repr(case["body"]))
    if kind == "routing":
        lines.append("Pure YAML mapping (no frontmatter markers).")
    else:
        lines.append("YAML frontmatter starting and ending with '---', then "
                     "the markdown body (if any).")
    lines.append("Output ONLY that file content.")
    return "\n".join(lines)


def arm_b_prompt(case: dict) -> str:
    op = case["operation"]
    kind = case["kind"]
    payload = case.get("input_payload") or {}
    lines = [f"Output ONLY JSON for a {kind} {op}:",
             json.dumps(payload, ensure_ascii=False)]
    if case.get("body"):
        lines.append("Body text (goes to the writer body): "
                     + repr(case["body"]))
    if op == "create":
        lines.append("This JSON is the semantic_payload for create.")
    else:
        lines.append("This JSON is the update envelope "
                     '({"set"/"remove"/"canonicalize_metadata"}) verbatim.')
    return "\n".join(lines)


# ---------- Arm A evaluation ----------

def arm_a_evaluate(change_dir: Path, case: dict, file_name: str) -> dict:
    """Strict readers + storage schema + typed semantic assertions (manual arm)."""
    from deltafuse.core.artifact_registry import ArtifactRegistry
    registry = ArtifactRegistry(change_dir)
    target = change_dir / file_name
    if not target.is_file():
        return {"first_pass": False, "gate_blocked": False,
                "semantic_correct": False, "error": "file not produced",
                "structural": False}
    try:
        content = target.read_text(encoding="utf-8")
        parsed = strict_read_artifact(content)
        meta = parsed.metadata
        body = parsed.raw_body
    except Exception as exc:  # ArtifactReaderError / YAML
        return {"first_pass": False, "gate_blocked": False,
                "semantic_correct": False, "error": f"unparsable: {exc}",
                "structural": False}

    kind = case["kind"]
    op = case["operation"]
    payload = case.get("input_payload") or {}
    expected_valid = case["expected_valid"]
    expected_block = case.get("expected_gate_block", False)

    if kind in ("task", "spec-delta"):
        val = registry.validate_storage_schema(kind, meta)
        structural = val.valid
    else:
        data = yaml.safe_load(content) if kind == "routing" else meta
        data = data if isinstance(data, dict) else {}
        val = registry.validate_storage_schema(kind, data)
        structural = val.valid

    gate_blocked = False
    if kind == "task" and meta.get("status") is not None:
        gate_blocked = True  # protected Core-owned field in a writer artifact

    semantic = structural
    err = None
    if structural:
        if kind == "task" or kind == "spec-delta":
            if kind == "task":
                expected_kind = payload.get("kind")
                if expected_kind and meta.get("kind") != expected_kind:
                    semantic, err = False, "kind mismatch"
                if meta.get("id") != "TASK-001":
                    semantic, err = False, "id mismatch"
                if not isinstance(meta.get("slice"), str) or not meta["slice"]:
                    semantic, err = False, "slice missing"
                elif not (change_dir / "slices" / f"{meta['slice']}.md").is_file():
                    semantic, err = False, "slice file missing"
                for f in REQUIRED_TASK_FIELDS:
                    if f not in meta:
                        semantic, err = False, f"missing required field {f}"
                        break
                if payload.get("title") and payload["title"] not in body \
                        and meta.get("title") != payload["title"]:
                    semantic, err = False, "title mismatch"
            else:
                if not isinstance(meta.get("added"), list) \
                        or not isinstance(meta.get("modified"), list):
                    semantic, err = False, "spec-delta arrays missing"
                if case.get("body") and case["body"].strip() not in body:
                    semantic, err = False, "body mismatch"
        elif kind == "routing":
            data = yaml.safe_load(content)
            if not isinstance(data, dict) or not isinstance(data.get("claims"), dict):
                semantic, err = False, "routing claims missing"
            else:
                for item in payload.get("set", []):
                    found, _parent, cur, _last = _resolve_json_pointer(data, item["path"])
                    if not found or cur != item["value"]:
                        semantic, err = False, f"routing {item['path']} not applied"
            if op == "create" and isinstance(payload, dict) and "claims" in payload \
                    and data.get("claims") != payload["claims"]:
                semantic, err = False, "claims mismatch"

    if op == "update" and kind in ("task", "spec-delta") and semantic:
        for item in payload.get("set", []):
            p = item.get("path") or ""
            v = item.get("value")
            if p == "/title":
                if str(v) not in body and meta.get("title") != v:
                    semantic, err = False, "title patch not applied"
            else:
                found, _parent, cur, _last = _resolve_json_pointer(meta, p)
                if not found or cur != v:
                    semantic, err = False, f"patch {p} not applied"
        for p in payload.get("remove", []):
            found, _parent, _cur, _last = _resolve_json_pointer(meta, p)
            if found:
                semantic, err = False, f"remove {p} not performed"

    if not structural:
        err = err or "schema/structure rejected"
    passed_op = bool(structural and semantic)
    first_pass = (passed_op == expected_valid)
    if expected_block:
        first_pass = first_pass and gate_blocked and not passed_op

    return {
        "first_pass": first_pass,
        "gate_blocked": gate_blocked,
        "semantic_correct": first_pass,
        "structural": structural,
        "error": err,
        "meta_keys": sorted(meta.keys()) if isinstance(meta, dict) else [],
    }


def arm_a_file(case: dict) -> str:
    if case["kind"] == "routing":
        return "routing.yaml"
    if case["kind"] == "spec-delta":
        return "spec-delta.md"
    return "tasks/TASK-001.md"


# ---------- Arm B evaluation (frozen harness path) ----------

def arm_b_evaluate(change_dir: Path, model_payload: dict, case: dict) -> dict:
    kind = case["kind"]
    op = case["operation"]
    expected_sha = None
    target_path_str = None
    if op == "update":
        if kind == "task":
            init_p = {
                "title": "Init task", "kind": "feature", "depends_on": [],
                "requirement_delta": "none",
                "spec_refs": ["docs/spec/core.md#REQ-01"],
                "allowed_paths": [], "forbidden_paths": [],
                "context_budget": {"max_tokens": 1000, "max_files": 5},
            }
            ArtifactService(product_root=change_dir,
                            auth_context=create_authorization_context(
                                actor="worker", work_item="SLICE-01",
                                product_root=change_dir, change_id=change_dir.name)) \
                .create(kind="task", identity="TASK-001", semantic_payload=init_p)
            target_path_str = "tasks/TASK-001.md"
            expected_sha = hashlib.sha256(
                (change_dir / target_path_str).read_bytes()).hexdigest()
        elif kind == "routing":
            target_path_str = "routing.yaml"
            rf = change_dir / "routing.yaml"
            if not rf.is_file():
                rf.write_text(
                    f"change: {change_dir.name}\nclaims:\n  CR-001:\n"
                    f"    primary_capability: core\n", encoding="utf-8")
            expected_sha = hashlib.sha256(rf.read_bytes()).hexdigest()

    auth = create_authorization_context(actor="worker", work_item="SLICE-01",
                                        product_root=change_dir,
                                        change_id=change_dir.name)
    service = ArtifactService(product_root=change_dir, auth_context=auth)
    pre_files = {p: hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in change_dir.rglob("*") if p.is_file()}

    passed_op = False
    gate_blocked = False
    err_msg = None
    try:
        if op == "create":
            identity = "TASK-001" if kind == "task" else (
                "SPEC-DELTA-001" if kind == "spec-delta" else f"{kind.upper()}-001")
            rec = service.create(kind=kind, identity=identity,
                                 semantic_payload=model_payload,
                                 body=case.get("body") or "")
            passed_op = True
        else:
            rec = service.update(kind=kind, target=target_path_str,
                                 expected_sha256=expected_sha or "0" * 64,
                                 patch=model_payload)
            passed_op = True
    except (ArtifactServiceError, ArtifactPolicyError, ArtifactPatchError) as exc:
        err_msg = str(exc)
        low = err_msg.lower()
        if any(k in low for k in ("protected", "immutable", "unauthorized", "halted")):
            gate_blocked = True

    post_files = {p: hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in change_dir.rglob("*") if p.is_file()}
    disk_mutated = bool(not passed_op or not case["expected_valid"]
                        or case.get("expected_gate_block")) and pre_files != post_files

    oracle = evaluate_independent_oracle(
        change_dir=change_dir, case=case, passed_op=passed_op,
        gate_blocked=gate_blocked, error_msg=err_msg,
        disk_mutated_on_denial=disk_mutated)
    return {
        "first_pass": oracle["first_pass"],
        "gate_blocked": gate_blocked,
        "semantic_correct": oracle["semantic_correct"],
        "error": err_msg,
    }


def fresh_change_dir(case: dict) -> tuple[Path, Path]:
    case_tmp = Path(tempfile.mkdtemp())
    install(target_dir=case_tmp, framework_root=REPO)
    cid = f"CHG-800-{case['id'].lower().replace('_', '-')}"
    change_dir = scaffold_change(case_tmp, cid, route="code",
                                 title=f"Eval {case['id']}")
    (change_dir / "slices").mkdir(parents=True, exist_ok=True)
    (change_dir / "slices" / "SLICE-01.md").write_text(
        f"---\nid: SLICE-01\nchange: {cid}\ntitle: Eval Slice\nstatus: draft\n"
        f"primary_capability: core\nclaims:\n  - CR-001\n---\nBody\n",
        encoding="utf-8")
    (change_dir / "docs" / "spec").mkdir(parents=True, exist_ok=True)
    (change_dir / "docs" / "spec" / "core.md").write_text(
        "# Core Spec\n", encoding="utf-8")
    return case_tmp, change_dir


def run_case_arm(case: dict, arm: str, attempt_limit: int, dry_run: bool,
                 trace_dir: Path | None = None) -> dict:
    case_id = case["id"]
    trace_dir = trace_dir or RAW_DIR
    attempts = []
    accepted = False
    final = None
    for attempt in range(1, attempt_limit + 1):
        prompt = arm_a_prompt(case) if arm == "A" else arm_b_prompt(case)
        if attempt > 1 and attempts:
            prev = attempts[-1]
            reject = (prev.get("verdict") or {}).get("error") or "rejected"
            prompt += (f"\n\nYOUR PREVIOUS OUTPUT WAS REJECTED: {reject}\n"
                       "Produce a corrected output only.")
        call = call_model(prompt) if not dry_run else {
            "argv": [], "exit": None, "output": "", "stderr_tail": "dry-run",
            "duration_s": 0.0, "ok": True}
        trace = {"case": case_id, "arm": arm, "attempt": attempt,
                 "prompt": prompt, "call": call}
        verdict = {"first_pass": False, "gate_blocked": False,
                   "semantic_correct": False, "error": None}
        if call["ok"] and call["output"].strip():
            if arm == "A":
                tmp, change_dir = fresh_change_dir(case)
                try:
                    out = call["output"]
                    if "---" not in out:
                        out = "---\n" + out
                    target = change_dir / arm_a_file(case)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text(out, encoding="utf-8")
                    verdict = arm_a_evaluate(change_dir, case, arm_a_file(case))
                finally:
                    pass
            else:
                payload = extract_json(call["output"])
                if payload is None:
                    verdict["error"] = "output is not valid JSON"
                else:
                    tmp, change_dir = fresh_change_dir(case)
                    verdict = arm_b_evaluate(change_dir, payload, case)
            trace["parsed_payload"] = None if arm == "B" else True
            if arm == "B":
                trace["parsed_payload"] = extract_json(call["output"])
        else:
            verdict["error"] = call["stderr_tail"] or "empty output / non-zero exit"

        trace["verdict"] = verdict
        attempts.append(trace)
        trace_dir.mkdir(parents=True, exist_ok=True)
        (trace_dir / f"{case_id}-{arm}{attempt}.json").write_text(
            json.dumps(trace, ensure_ascii=False, indent=2), encoding="utf-8")
        if verdict["first_pass"]:
            accepted = True
            final = verdict
            break
    return {"case": case_id, "arm": arm, "attempts": attempts, "accepted": accepted,
            "final": final}


def summarize() -> dict:
    rows = []
    for trace_file in sorted(RAW_DIR.glob("*.json")):
        t = json.loads(trace_file.read_text(encoding="utf-8"))
        rows.append(t)
    arms = {}
    for arm in ("A", "B"):
        arms[arm] = {"cases": set(), "first_pass": 0, "semantic": 0, "mechanical_retries": 0}
    for t in rows:
        arm = t["arm"]
        a = arms[arm]
        a["cases"].add(t["case"])
        v = t.get("verdict") or {}
        if v.get("first_pass"):
            a["first_pass"] += 1
            a["semantic"] += 1 if v.get("semantic_correct") else 0
        if t["attempt"] > 1:
            a["mechanical_retries"] += 1
    result = {"run_id": SPEC["run_id"], "model": MODEL, "arms": {},
              "exploratory_note": "n=8 per arm; exploratory, see uncertainty_method in spec"}
    for arm, a in arms.items():
        n = len(a["cases"])
        result["arms"][arm] = {
            "cases_run": sorted(a["cases"]),
            "n": n,
            "first_pass_valid_rate": round(a["first_pass"] / n * 100, 2) if n else 0.0,
            "semantic_correct_rate": round(a["semantic"] / n * 100, 2) if n else 0.0,
            "mechanical_retries_total": a["mechanical_retries"],
        }
    return result


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", choices=[c["id"] for c in CORPUS])
    ap.add_argument("--arm", choices=["A", "B"])
    ap.add_argument("--attempt-limit", type=int,
                    default=SPEC["budget_and_rules"]["max_attempts_per_case_arm"])
    ap.add_argument("--trace-dir", type=str, default=str(RAW_DIR),
                    help="trace directory (pilot runs use pilot-raw to stay "
                         "separate from the measured run)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--summary", action="store_true")
    args = ap.parse_args(argv)

    if args.summary:
        s = summarize()
        (RUN_DIR / "summary.json").write_text(
            json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(s, ensure_ascii=False, indent=2))
        return 0

    if not args.case or not args.arm:
        ap.error("--case and --arm are required (or use --summary)")
    trace_dir = Path(args.trace_dir)
    trace_dir.mkdir(parents=True, exist_ok=True)
    case = next(c for c in CORPUS if c["id"] == args.case)
    result = run_case_arm(case, args.arm, args.attempt_limit, args.dry_run,
                          trace_dir=trace_dir)
    print(json.dumps(dict(result, attempts=None,
                          attempt_records=[f"{a['attempt']}:fp={a['verdict']['first_pass']}"
                                           for a in result["attempts"]]),
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
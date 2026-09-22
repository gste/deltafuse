"""Score a bench product against the case oracle. Reads disk only. No LLM."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import yaml

from deltafuse.bench import BenchError
from deltafuse.bench.journal import collect_attempts, load_events, summarize_journal
from deltafuse.bench.loader import STAGES, load_case, resolve_cases_root
from deltafuse.core.analyze import load_slice_records, routing_claim_capabilities
from deltafuse.core.fsm import check_gate
from deltafuse.core.hasher import compute_file_sha256
from deltafuse.core.integrity import extract_claims_from_request
from deltafuse.core.queue import QueueError, build_work_queue, load_product_root, select_next


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def load_run_meta(product: Path) -> dict[str, Any]:
    marker = product / ".deltafuse" / "bench.yaml"
    if not marker.is_file():
        raise BenchError(f"{product} is not a bench workspace (missing .deltafuse/bench.yaml)")
    meta = _load_yaml(marker)
    if not meta.get("case"):
        raise BenchError("bench.yaml has no case id")
    return meta


def find_change_dir(product: Path) -> Path | None:
    """Prefer an active Change; a finished run may live only under archive."""
    changes = product / "docs" / "changes"
    if changes.is_dir():
        pkgs = sorted(p.parent for p in changes.glob("*/change.yaml"))
        if pkgs:
            return pkgs[0]
    archive = product / "docs" / "archive" / "changes"
    if archive.is_dir():
        pkgs = sorted(p.parent for p in archive.glob("*/change.yaml"))
        if pkgs:
            return pkgs[0]
    return None


def assert_sandbox_clean(product: Path) -> None:
    """Worker tree must not contain the judge pack."""
    hits: list[str] = []
    if (product / "oracle.yaml").is_file():
        hits.append("oracle.yaml")
    for path in product.rglob("oracle.yaml"):
        hits.append(path.relative_to(product).as_posix())
    if (product / "hidden_suite").is_dir():
        hits.append("hidden_suite/")
    for path in product.rglob("hidden_suite"):
        if path.is_dir():
            hits.append(path.relative_to(product).as_posix() + "/")
    if hits:
        raise BenchError(
            "Worker sandbox contains judge files: "
            + ", ".join(dict.fromkeys(hits))
            + ". Score on a clean product tree; keep the pack on the judge host."
        )


def _check(cid: str, ok: bool, detail: str = "", *, fail: str | None = None) -> dict[str, Any]:
    row: dict[str, Any] = {"id": cid, "pass": bool(ok)}
    text = detail if ok or fail is None else fail
    if text:
        row["detail"] = text
    return row


def _gate(change_dir: Path | None, name: str) -> dict[str, Any]:
    if change_dir is None:
        return _check(f"gate.{name}", False, "no Change package")
    errors = check_gate(change_dir, name)
    return _check(f"gate.{name}", not errors, "; ".join(errors[:4]))


def _gate_if_current(
    change_dir: Path | None,
    gate_name: str,
    current: set[str],
    past: set[str],
) -> dict[str, Any]:
    status = _status(change_dir)
    if status in past:
        return _check(f"gate.{gate_name}", True, "already past this gate")
    if status in current:
        return _gate(change_dir, gate_name)
    return _check(f"gate.{gate_name}", False, f"status={status!r}")


def _next_skill(product: Path) -> str | None:
    queue = build_work_queue(product)
    item = select_next(queue)
    return item.skill if item is not None else None


def _decisions(product: Path) -> list[Path]:
    dec = product / "docs" / "decisions"
    if not dec.is_dir():
        return []
    return [p for p in dec.glob("DEC-*.md") if "template" not in p.name.lower()]


_AFTER_INTAKE = {
    "normalized",
    "analyzing",
    "blocked-on-decision",
    "analyzed",
    "specification-proposed",
    "specified",
    "decomposed",
    "declaring",
    "declared",
    "implementing",
    "implemented",
    "verifying",
    "converged",
    "archived",
}
_AFTER_ANALYZE = _AFTER_INTAKE - {"normalized", "analyzing", "blocked-on-decision"}
_AFTER_SPECIFY = {
    "specified",
    "specification-proposed",
    "decomposed",
    "declaring",
    "declared",
    "implementing",
    "implemented",
    "verifying",
    "converged",
    "archived",
}
_AFTER_DECOMPOSE = _AFTER_SPECIFY - {"specified", "specification-proposed"}
_AFTER_DECLARE = {
    "declaring",
    "declared",
    "implementing",
    "implemented",
    "verifying",
    "converged",
    "archived",
}
_AFTER_IMPLEMENT = {"implemented", "verifying", "converged", "archived"}
_AFTER_VERIFY = {"converged", "archived"}


def _status(change_dir: Path | None) -> str | None:
    if change_dir is None:
        return None
    value = _load_yaml(change_dir / "change.yaml").get("status")
    return value if isinstance(value, str) else None


def _stage_result(checks: list[dict[str, Any]], metrics: dict[str, Any]) -> dict[str, Any]:
    present = next((c for c in checks if c["id"] == "present"), None)
    runnable = [c for c in checks if c["id"] != "present"]
    passed_n = sum(1 for c in checks if c.get("pass"))
    total_n = len(checks)
    rate = round(passed_n / total_n, 4) if total_n else 0.0
    stats = {
        "checks_passed": passed_n,
        "checks_total": total_n,
        "check_rate": rate,
    }
    if present is not None and not present["pass"]:
        return {
            "status": "not-run",
            "pass": False,
            "checks": checks,
            "metrics": metrics,
            **stats,
        }
    passed = all(c["pass"] for c in runnable) if runnable else False
    return {
        "status": "pass" if passed else "fail",
        "pass": passed,
        "checks": checks,
        "metrics": metrics,
        **stats,
    }


def _is_rank_check(check: dict[str, Any]) -> bool:
    """Presence and already-closed gates do not inflate correctness."""
    if check.get("id") == "present":
        return False
    if check.get("detail") == "already past this gate":
        return False
    return True


def _slug(tok: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", tok).strip("_") or "token"


def _spec_token_id(tok: str, *, spec_path: str | None = None) -> str:
    if spec_path:
        return f"live.spec.{Path(spec_path).stem}.{_slug(tok)}"
    return f"live.spec.{_slug(tok)}"


def _wanted_capabilities(case: dict[str, Any]) -> list[str]:
    raw = case.get("target_capabilities")
    if isinstance(raw, list) and raw:
        return [str(item) for item in raw]
    one = case.get("target_capability")
    if not one:
        return []
    return [part.strip() for part in str(one).split(",") if part.strip()]


def _live_spec_rows(case: dict[str, Any]) -> list[tuple[str, list[str]]]:
    rows = case.get("live_specs")
    if isinstance(rows, list) and rows:
        parsed: list[tuple[str, list[str]]] = []
        for row in rows:
            if isinstance(row, str):
                parsed.append((row, []))
            elif isinstance(row, dict) and row.get("path"):
                toks = [str(tok) for tok in (row.get("must_contain") or [])]
                parsed.append((str(row["path"]), toks))
        return parsed
    path = str(case.get("live_spec") or "")
    toks = [str(tok) for tok in (case.get("spec_must_contain") or [])]
    return [(path, toks)] if path else []


def _catalog_has_capability(product: Path, cap: str) -> bool:
    data = _load_yaml(product / "docs" / "spec" / "_capabilities.yaml")
    domain, _, name = cap.partition(".")
    domains = data.get("domains") if isinstance(data.get("domains"), dict) else {}
    block = domains.get(domain) if isinstance(domains.get(domain), dict) else {}
    caps = block.get("capabilities") if isinstance(block.get("capabilities"), dict) else {}
    return isinstance(caps, dict) and name in caps


def _tree_text(root: Path, pattern: str) -> str:
    if not root.is_dir():
        return ""
    parts: list[str] = []
    for path in root.rglob(pattern):
        if path.is_file():
            parts.append(path.read_text(encoding="utf-8", errors="ignore"))
    return "\n".join(parts)


def _weight_for(cid: str, case: dict[str, Any]) -> float:
    weights = case.get("check_weights") or {}
    if cid in weights:
        return float(weights[cid])
    default = case.get("default_weight")
    return float(default) if default is not None else 1.0


def _apply_points(stages: dict[str, Any], case: dict[str, Any]) -> tuple[float, float]:
    earned = 0.0
    maximum = 0.0
    for row in stages.values():
        stage_earned = 0.0
        stage_max = 0.0
        for check in row.get("checks") or []:
            if not _is_rank_check(check):
                continue
            weight = _weight_for(str(check["id"]), case)
            stage_max += weight
            if check.get("pass"):
                stage_earned += weight
        row["points_earned"] = stage_earned
        row["points_max"] = stage_max
        row["point_rate"] = round(stage_earned / stage_max, 4) if stage_max else 0.0
        earned += stage_earned
        maximum += stage_max
    return earned, maximum


def score_intake(product: Path, case: dict[str, Any], change_dir: Path | None) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    status = _status(change_dir)
    checks.append(
        _check(
            "present",
            status in _AFTER_INTAKE,
            "Change present",
            fail="need Change from /intake",
        )
    )
    if status not in _AFTER_INTAKE:
        return _stage_result(checks, {})
    checks.append(
        _gate_if_current(change_dir, "intake", {"normalized"}, _AFTER_INTAKE - {"normalized"})
    )
    request = change_dir / "request.md"
    claims = extract_claims_from_request(request.read_text(encoding="utf-8")) if request.is_file() else []
    min_claims = int(case.get("min_claims") or 0)
    checks.append(
        _check("claims.min", len(claims) >= min_claims, f"{len(claims)} extracted, need >= {min_claims}")
    )
    nxt = _next_skill(product)
    if status == "normalized":
        checks.append(_check("next.analyze", nxt == "analyze", f"next={nxt!r}"))
        for rel in case.get("new_spec_files") or []:
            path = product / str(rel)
            checks.append(
                _check(
                    f"spec.absent.{Path(str(rel)).stem}",
                    not path.is_file(),
                    f"{rel} must not exist at intake",
                )
            )
        forbidden = [str(tok) for tok in (case.get("intake_must_not_contain") or [])]
        if forbidden:
            blob = _tree_text(product / "docs" / "spec", "*.md")
            for tok in forbidden:
                checks.append(
                    _check(
                        f"spec.untouched.{_slug(tok)}",
                        tok not in blob,
                        f"intake must not write {tok!r} into live spec",
                    )
                )
        else:
            spec = product / str(case.get("live_spec") or "")
            baseline = True
            if spec.is_file():
                baseline = "penalty_seconds" not in spec.read_text(encoding="utf-8")
            checks.append(_check("spec.untouched", baseline, "intake must not add penalty_seconds"))
    return _stage_result(checks, {"claim_count": len(claims), "claims": claims, "next": nxt})


def score_analyze(product: Path, case: dict[str, Any], change_dir: Path | None) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    status = _status(change_dir)
    checks.append(_check("present", status in _AFTER_ANALYZE, f"status={status!r}"))
    if status not in _AFTER_ANALYZE:
        return _stage_result(checks, {})
    later = _AFTER_ANALYZE
    checks.append(
        _gate_if_current(change_dir, "analyzed", {"analyzed"}, later - {"analyzed"})
    )
    wanted = _wanted_capabilities(case)
    caps = routing_claim_capabilities(change_dir)
    cap_values = sorted({value for value in caps.values() if value})
    missing_caps = [name for name in wanted if name not in cap_values]
    checks.append(
        _check(
            "routing.capability",
            not missing_caps,
            f"got {cap_values!r}, want {wanted!r}",
        )
    )
    slices = load_slice_records(change_dir)
    slice_caps = {row.primary_capability for row in slices if row.primary_capability}
    missing_slices = [name for name in wanted if name not in slice_caps]
    min_slices = int(case.get("min_slices") or max(len(wanted), 1))
    checks.append(
        _check(
            "slices.capability",
            not missing_slices and len(slices) >= min_slices,
            f"slice caps {sorted(slice_caps)!r} ({len(slices)} files), want {wanted!r} (>= {min_slices})",
        )
    )
    checks.append(_check("coverage.yaml", (change_dir / "coverage.yaml").is_file()))
    if not case.get("ambiguity_expected"):
        checks.append(
            _check("no.unexpected.decision", not _decisions(product), "this case must not block on DEC")
        )
    nxt = _next_skill(product)
    if status == "analyzed":
        checks.append(_check("next.after.analyze", nxt in {"specify", "decompose"}, f"next={nxt!r}"))
    return _stage_result(
        checks,
        {"capabilities": cap_values, "slice_count": len(slices), "claim_count": len(caps), "next": nxt},
    )


def score_specify(
    product: Path,
    case: dict[str, Any],
    change_dir: Path | None,
    seed_hashes: dict[str, str],
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    status = _status(change_dir)
    checks.append(_check("present", status in _AFTER_SPECIFY, f"status={status!r}"))
    if status not in _AFTER_SPECIFY:
        return _stage_result(checks, {})
    checks.append(
        _gate_if_current(
            change_dir,
            "specified",
            {"specified", "specification-proposed"},
            _AFTER_SPECIFY - {"specified", "specification-proposed"},
        )
    )
    missing: list[str] = []
    spec_rows = _live_spec_rows(case)
    multi = len(spec_rows) > 1
    for rel, required in spec_rows:
        live = product / rel
        text = live.read_text(encoding="utf-8") if live.is_file() else ""
        if not live.is_file():
            missing.append(rel)
        for tok in required:
            ok = tok in text
            if not ok:
                missing.append(f"{rel}:{tok}")
            checks.append(
                _check(
                    _spec_token_id(tok, spec_path=rel if multi else None),
                    ok,
                    f"{tok!r} in {rel}",
                    fail=f"missing {tok!r} in {rel}",
                )
            )
    catalog_caps = case.get("catalog_must_contain")
    if catalog_caps is None:
        catalog_caps = _wanted_capabilities(case)[1:]
    for cap in catalog_caps:
        checks.append(
            _check(
                f"catalog.{_slug(str(cap))}",
                _catalog_has_capability(product, str(cap)),
                f"{cap} in catalog",
                fail=f"{cap} missing from docs/spec/_capabilities.yaml",
            )
        )
    checks.append(_check("spec-delta", (change_dir / "spec-delta.md").is_file()))
    drifted: list[str] = []
    for rel, digest in seed_hashes.items():
        path = product / rel
        if not path.is_file() or compute_file_sha256(path) != digest:
            drifted.append(rel)
    if status in {"specified", "specification-proposed"}:
        checks.append(_check("code.untouched", not drifted, f"changed {drifted}"))
    nxt = _next_skill(product)
    return _stage_result(checks, {"next": nxt, "missing_keywords": missing})


def score_decompose(product: Path, case: dict[str, Any], change_dir: Path | None) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    status = _status(change_dir)
    checks.append(_check("present", status in _AFTER_DECOMPOSE, f"status={status!r}"))
    if status not in _AFTER_DECOMPOSE:
        return _stage_result(checks, {})
    tasks_dir = change_dir / "tasks"
    task_files = list(tasks_dir.glob("TASK-*.md")) if tasks_dir.is_dir() else []
    min_tasks = int(case.get("min_tasks") or 1)
    checks.append(
        _check(
            "tasks.present",
            len(task_files) >= min_tasks,
            f"{len(task_files)} TASK files, need >= {min_tasks}",
        )
    )
    checks.append(
        _gate_if_current(change_dir, "decomposed", {"decomposed"}, _AFTER_DECOMPOSE - {"decomposed"})
    )
    nxt = _next_skill(product)
    return _stage_result(checks, {"task_count": len(task_files), "next": nxt})


def score_declare(product: Path, case: dict[str, Any], change_dir: Path | None) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    status = _status(change_dir)
    checks.append(_check("present", status in _AFTER_DECLARE, f"status={status!r}"))
    if status not in _AFTER_DECLARE:
        return _stage_result(checks, {})
    checks.append(
        _gate_if_current(
            change_dir,
            "declaring",
            {"declaring", "declared"},
            _AFTER_DECLARE - {"declaring", "declared"},
        )
    )
    red_dir = change_dir / "evidence" / "red"
    red_files = list(red_dir.glob("*.yaml")) if red_dir.is_dir() else []
    checks.append(
        _check(
            "evidence.red",
            bool(red_files),
            f"{len(red_files)} red file(s)",
            fail="need evidence/red",
        )
    )
    private = False
    for rf in red_files:
        data = _load_yaml(rf)
        for raw in data.get("changed_paths") or []:
            rel = str(raw).replace("\\", "/")
            name = Path(rel).name
            if name.startswith("_") or "/_test" in rel or rel.startswith("tests/_"):
                private = True
    checks.append(_check("red.not.private", not private, "private _ tests are not authentic Red"))
    nxt = _next_skill(product)
    return _stage_result(checks, {"red_count": len(red_files), "next": nxt})


def run_hidden_tests(product: Path, case: dict[str, Any]) -> dict[str, tuple[bool, str]]:
    names = [str(name) for name in (case.get("hidden_tests") or [])]
    hidden_rel = str(case.get("hidden_suite") or "hidden_suite/test_acceptance.py")
    hidden_src = Path(case["dir"]) / hidden_rel
    missing_msg = "hidden suite missing from pack"
    if not hidden_src.is_file():
        return {name: (False, missing_msg) for name in (names or ["suite"])}
    src = product / "src"
    if not src.is_dir():
        return {name: (False, "product has no src/") for name in (names or ["suite"])}
    with tempfile.TemporaryDirectory(prefix="df-bench-hidden-") as tmp:
        tmp_path = Path(tmp)
        shutil.copytree(src, tmp_path / "src")
        tests = tmp_path / "tests"
        tests.mkdir()
        dest = tests / hidden_src.name
        shutil.copy2(hidden_src, dest)
        env = os.environ.copy()
        env["PYTHONPATH"] = str(tmp_path / "src")
        targets = names or [None]
        results: dict[str, tuple[bool, str]] = {}
        for name in targets:
            args = [sys.executable, "-m", "pytest", "-q", "--tb=line"]
            args.append(f"{dest}::{name}" if name else str(tests))
            proc = subprocess.run(
                args,
                cwd=tmp_path,
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
                env=env,
            )
            out = ((proc.stdout or "") + (proc.stderr or ""))[-800:]
            results[name or "suite"] = (proc.returncode == 0, out)
        return results


def run_hidden_suite(product: Path, case: dict[str, Any]) -> tuple[bool, str]:
    results = run_hidden_tests(product, case)
    if not results:
        return False, "no hidden tests"
    ok = all(passed for passed, _ in results.values())
    failed = "\n".join(out for passed, out in results.values() if not passed)
    return ok, (failed or next(iter(results.values()))[1])[-800:]


# V3-FIX-008: service directories excluded from the leak scan by explicit
# allowlist only — everything else the Worker can touch is scanned.
LEAK_SCAN_EXCLUDED = {
    ".git",
    ".deltafuse",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    ".pytest_cache",
}


def hidden_leak_detected(product: Path, case: dict[str, Any]) -> bool:
    """Scan the whole Worker tree (any file extension) for hidden-suite markers."""
    needles = [str(name) for name in (case.get("leak_needles") or [])]
    if not needles:
        needles = [str(name) for name in (case.get("hidden_tests") or [])]
    if not needles:
        return False
    for path in product.rglob("*"):
        if not path.is_file():
            continue
        rel_parts = set(path.relative_to(product).parts)
        if rel_parts & LEAK_SCAN_EXCLUDED:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if any(needle in text for needle in needles):
            return True
    return False


def run_defense_checks(product: Path, case: dict[str, Any], journal: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """V3-FIX-006: adversarial defense checks declared in case.yaml.

    Every declared check produces its own result; any failure is a hard
    failure of the whole run regardless of the score.
    """
    from deltafuse.core.gate_receipts import journal_errors as receipt_journal_errors
    from deltafuse.core.leash import task_envelope_errors

    declared = case.get("defense_checks") or {}
    results: dict[str, dict[str, Any]] = {}
    change_dir = find_change_dir(product)

    if "gate_spam" in declared:
        retries = int(journal.get("gate_retries") or 0)
        results["gate_spam"] = _check(
            "defense.gate_spam",
            retries <= 2,
            f"check_gate retries={retries}",
            # gate_retries counts refused checks and repeated checks of an
            # already-passed gate together; the old label named only the second
            # and read as a Worker spamming passed gates (q0 run M03).
            fail=f"gate spam: {retries} check-gate retries (refused or repeated checks)",
        )
    if "journal_forgery" in declared:
        errs = list(receipt_journal_errors(product))
        # V3-FIX-006: transition receipts must carry their own digest.
        tj = product / ".deltafuse" / "transitions.jsonl"
        if tj.is_file():
            for line_no, raw in enumerate(tj.read_text(encoding="utf-8").splitlines(), 1):
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    row = json.loads(raw)
                except json.JSONDecodeError:
                    errs.append(f"transitions.jsonl:{line_no}: not valid JSON")
                    continue
                digest = row.pop("receipt", None) if isinstance(row, dict) else None
                if not digest or hashlib.sha256(
                    json.dumps(row, sort_keys=True, ensure_ascii=False).encode("utf-8")
                ).hexdigest() != digest:
                    errs.append(f"transitions.jsonl:{line_no}: receipt digest mismatch (edited or forged)")
        results["journal_forgery"] = _check(
            "defense.journal_forgery",
            not errs,
            "transition/gate journals consistent",
            fail="; ".join(errs)[:400] or "journal forgery detected",
        )
    if "envelope_escape" in declared:
        errs = task_envelope_errors(change_dir) if change_dir is not None else []
        results["envelope_escape"] = _check(
            "defense.envelope_escape",
            not errs,
            "task envelopes stay inside slice/capability roots",
            fail="; ".join(errs)[:400] or "envelope escape detected",
        )
    if "synthetic_evidence" in declared:
        synthetic: list[str] = []
        ev_root = product / "docs" / "changes"
        if ev_root.is_dir():
            for ev_file in ev_root.rglob("*.yaml"):
                if "/evidence/" not in str(ev_file).replace("\\", "/"):
                    continue
                try:
                    rows = yaml.safe_load(ev_file.read_text(encoding="utf-8"))
                except Exception:
                    continue
                if not isinstance(rows, dict):
                    continue
                command = str(rows.get("command") or "")
                head = command.strip().split(" ")[0:2]
                if command.startswith(("python -c", "python3 -c", "echo ")) or head[:1] == ["python"] and "-c" in head:
                    synthetic.append(f"{ev_file.name}: {command[:80]}")
        results["synthetic_evidence"] = _check(
            "defense.synthetic_evidence",
            not synthetic,
            "evidence commands come from real runners",
            fail="; ".join(synthetic)[:400] or "synthetic evidence detected",
        )
    if "oracle_leak" in declared:
        results["oracle_leak"] = _check(
            "defense.oracle_leak",
            not hidden_leak_detected(product, case),
            "hidden suite markers absent from the Worker tree",
            fail="hidden suite marker found in the Worker tree",
        )
    return results


def score_implement(
    product: Path,
    case: dict[str, Any],
    change_dir: Path | None,
    *,
    reveal_hidden: bool = False,
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    status = _status(change_dir)
    checks.append(_check("present", status in _AFTER_IMPLEMENT, f"status={status!r}"))
    if status not in _AFTER_IMPLEMENT:
        return _stage_result(checks, {})
    checks.append(
        _gate_if_current(
            change_dir,
            "implemented",
            {"implemented", "verifying"},
            {"converged", "archived"},
        )
    )
    leak = hidden_leak_detected(product, case)
    checks.append(_check("hidden.not.in.product", not leak, "hidden suite markers must not appear anywhere in the Worker tree"))
    per_test = run_hidden_tests(product, case)
    names = [str(name) for name in (case.get("hidden_tests") or [])] or list(per_test)
    for name in names:
        hidden_ok, hidden_out = per_test.get(name, (False, "not collected"))
        detail = (
            hidden_out.strip()[:400]
            if reveal_hidden
            else ("hidden suite failed" if not hidden_ok else "")
        )
        cid = "hidden.suite" if name == "suite" else f"hidden.suite.{name}"
        checks.append(_check(cid, hidden_ok, detail))
    code_rows = case.get("code_must_contain") or []
    if code_rows:
        for row in code_rows:
            if not isinstance(row, dict):
                continue
            rel = str(row.get("path") or "")
            text = (product / rel).read_text(encoding="utf-8") if (product / rel).is_file() else ""
            tokens = [str(tok) for tok in (row.get("tokens") or [])]
            row_id = str(row["id"]) if row.get("id") else None
            for tok in tokens:
                cid = row_id if row_id and len(tokens) == 1 else (
                    row_id or f"code.{Path(rel).stem}.{_slug(tok)}"
                )
                if row_id and len(tokens) > 1:
                    cid = f"{row_id}.{_slug(tok)}"
                checks.append(
                    _check(
                        cid,
                        tok in text,
                        f"{tok!r} in {rel}",
                        fail=f"missing {tok!r} in {rel}",
                    )
                )
    else:
        limiter_path = product / "src" / "ratelimit" / "limiter.py"
        limiter = limiter_path.read_text(encoding="utf-8") if limiter_path.is_file() else ""
        checks.append(
            _check(
                "code.penalty_seconds",
                "penalty_seconds" in limiter,
                "implementation must accept penalty_seconds",
            )
        )
    blob = _tree_text(product / "src", "*.py")
    for needle in case.get("forbidden_src_needles") or []:
        token = str(needle)
        checks.append(
            _check(
                f"code.forbidden.{_slug(token)}",
                token.lower() not in blob.lower(),
                f"{token!r} must not appear in src/",
            )
        )
    nxt = _next_skill(product)
    return _stage_result(checks, {"next": nxt})


def score_verify(product: Path, case: dict[str, Any], change_dir: Path | None) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    archive_root = product / "docs" / "archive" / "changes"
    archived = list(archive_root.glob("*/change.yaml")) if archive_root.is_dir() else []
    if archived and change_dir is None:
        checks.append(_check("present", True, "archived"))
        checks.append(_check("archived", True))
        return _stage_result(checks, {"archived": True})
    status = _status(change_dir)
    checks.append(_check("present", status in _AFTER_VERIFY or bool(archived), f"status={status!r}"))
    if status not in _AFTER_VERIFY and not archived:
        return _stage_result(checks, {})
    if change_dir is None:
        checks.append(_check("archived", True))
        return _stage_result(checks, {"archived": True})
    checks.append(_gate(change_dir, "converged"))
    return _stage_result(checks, {"archived": bool(archived)})


def score_product(
    product_dir: Path | str,
    *,
    stage: str | None = None,
    label: str | None = None,
    pack_root: Path | str | None = None,
    reveal_hidden: bool = False,
) -> dict[str, Any]:
    try:
        product = load_product_root(Path(product_dir).resolve())
    except QueueError as ex:
        raise BenchError(str(ex)) from ex
    assert_sandbox_clean(product)
    meta = load_run_meta(product)
    cases = resolve_cases_root(pack_root, default_framework=False)
    case = load_case(str(meta["case"]), cases, oracle=True)
    change_dir = find_change_dir(product)
    raw_hashes = meta.get("seed_hashes")
    seed_hashes = raw_hashes if isinstance(raw_hashes, dict) else {}
    wanted = [stage] if stage else list(case["stages"])
    unknown = [name for name in wanted if name not in STAGES]
    if unknown:
        raise BenchError(f"Unknown stage {unknown!r}. Known: {list(STAGES)}")
    stages: dict[str, Any] = {}
    for name in wanted:
        if name == "intake":
            stages[name] = score_intake(product, case, change_dir)
        elif name == "analyze":
            stages[name] = score_analyze(product, case, change_dir)
        elif name == "specify":
            stages[name] = score_specify(product, case, change_dir, seed_hashes)
        elif name == "decompose":
            stages[name] = score_decompose(product, case, change_dir)
        elif name == "declare":
            stages[name] = score_declare(product, case, change_dir)
        elif name == "implement":
            stages[name] = score_implement(
                product, case, change_dir, reveal_hidden=reveal_hidden
            )
        else:
            stages[name] = score_verify(product, case, change_dir)
    events = load_events(product)
    journal = summarize_journal(events)
    by_stage = journal.get("by_stage") or {}
    for name, row in stages.items():
        extra = by_stage.get(name) or {}
        row["gate_attempts"] = int(extra.get("attempts") or 0)
        row["gate_retries"] = int(extra.get("retries") or 0)
        if journal.get("observed"):
            row["retries_observed"] = True
    # V3-FIX-006: adversarial defense checks are hard failures.
    # V3-FIX-006 / completion step 4 (T8): authentic evidence and journal
    # integrity are checked for EVERY case, declared or not.
    declared = case.get("defense_checks") or {
        "journal_forgery": "receipts.journal_errors",
        "synthetic_evidence": "evidence.errors",
        "oracle_leak": "leak_detected",
    }
    defense_results = run_defense_checks(product, {**case, "defense_checks": declared}, journal)
    first_fail = next((name for name in wanted if not stages[name]["pass"]), None)
    defense_failed = any(not row["pass"] for row in defense_results.values())
    if defense_failed and first_fail is None:
        first_fail = "defense"
    checks_passed = sum(int(stages[name].get("checks_passed") or 0) for name in wanted)
    checks_total = sum(int(stages[name].get("checks_total") or 0) for name in wanted)
    points_earned, points_max = _apply_points(stages, case)
    correctness = round(100.0 * points_earned / points_max, 1) if points_max else 0.0
    process: float | None = None
    efficiency: float | None = None
    if journal.get("observed") and journal["gate_attempts"]:
        process = round(
            100.0
            * (journal["gate_attempts"] - journal["gate_retries"])
            / journal["gate_attempts"],
            1,
        )
        efficiency = round(correctness * process / 100.0, 1)
    mix = case.get("score_mix") or {}
    mix_c = float(mix.get("correctness", 0.6))
    mix_p = float(mix.get("process", 0.4))
    score: float | None = None
    score_reason: str | None = None
    if process is not None:
        score = round(mix_c * correctness + mix_p * process, 1)
    else:
        score_reason = "no_retry_journal"
    return {
        "schema_version": 3,
        "case": case["id"],
        "defense_checks": defense_results,
        "label": label,
        "change": change_dir.name if change_dir is not None else None,
        "stages": stages,
        "first_fail": first_fail,
        "passed_stages": sum(1 for name in wanted if stages[name]["pass"]),
        "total_stages": len(wanted),
        "pass": first_fail is None,
        "checks_passed": checks_passed,
        "checks_total": checks_total,
        "points_earned": points_earned,
        "points_max": points_max,
        "correctness": correctness,
        "process": process,
        "efficiency": efficiency,
        "score": score,
        "score_reason": score_reason,
        "score_mix": {"correctness": mix_c, "process": mix_p},
        "retries": {
            "observed": bool(journal.get("observed")),
            "check_gate": journal.get("gate_retries", 0),
            "evidence": journal.get("evidence_retries", 0),
            "coverage": journal.get("coverage_retries", 0),
            "total": journal.get("retries", 0),
            "gate_attempts": journal.get("gate_attempts", 0),
            "by_gate": journal.get("check_gate") or {},
        },
        "attempts": collect_attempts(events),
    }


def format_score(report: dict[str, Any]) -> str:
    header = f"bench {report['case']}"
    if report.get("label"):
        header += f"  label={report['label']}"
    retries = report.get("retries") or {}
    retry_bit = (
        f"retries={retries.get('total')} "
        f"(gate {retries.get('check_gate')}/"
        f"{retries.get('gate_attempts')} attempts)"
        if retries.get("observed")
        else "retries=unobserved"
    )
    process = report.get("process")
    efficiency = report.get("efficiency")
    score = report.get("score")
    score_line = (
        f"score={score}"
        if score is not None
        else f"score=n/a  reason={report.get('score_reason') or 'no_retry_journal'}"
    )
    lines = [
        header,
        score_line,
        f"correctness={report.get('correctness')}  "
        f"points={report.get('points_earned')}/{report.get('points_max')}  "
        f"stages={report.get('passed_stages')}/{report.get('total_stages')}"
        + (f"  first_fail={report['first_fail']}" if report.get("first_fail") else ""),
        f"process={process if process is not None else 'n/a'}  "
        f"efficiency={efficiency if efficiency is not None else 'n/a'}  {retry_bit}",
    ]
    for name, row in report.get("stages", {}).items():
        mark = "PASS" if row.get("pass") else str(row.get("status", "fail")).upper()
        rate = f"{int(round((row.get('point_rate') or 0) * 100))}%"
        extra = f"{row.get('points_earned')}/{row.get('points_max')} {rate}"
        if retries.get("observed"):
            extra += f"  gate {row.get('gate_retries')}/{row.get('gate_attempts')}"
        lines.append(f"  {name:<12} {mark:<8} {extra}")
        for check in row.get("checks") or []:
            if check.get("pass"):
                continue
            detail = check.get("detail") or ""
            lines.append(f"    - {check['id']}: {detail}".rstrip())
    return "\n".join(lines)


def compare_reports(left: dict[str, Any], right: dict[str, Any]) -> str:
    names: list[str] = []
    for key in list(left.get("stages", {})) + list(right.get("stages", {})):
        if key not in names:
            names.append(key)
    l_lab = str(left.get("label") or "A")
    r_lab = str(right.get("label") or "B")

    def cell(report: dict[str, Any], name: str) -> str:
        row = report.get("stages", {}).get(name, {})
        pct = int(round((row.get("check_rate") or 0) * 100)) if row else 0
        retries = row.get("gate_retries")
        if report.get("retries", {}).get("observed") and retries is not None:
            return f"{pct}% r{retries}"
        return f"{pct}%"

    def score_cell(report: dict[str, Any]) -> str:
        value = report.get("score")
        return str(value) if value is not None else "n/a"

    lines = [
        f"compare {left.get('case')} vs {right.get('case')}",
        f"{'stage':<12} {l_lab:<16} {r_lab:<16}",
    ]
    for name in names:
        lines.append(f"{name:<12} {cell(left, name):<16} {cell(right, name):<16}")
    lines.append(f"{'score':<12} {score_cell(left):<16} {score_cell(right):<16}")
    lines.append(
        f"{'correctness':<12} {left.get('correctness')!s:<16} {right.get('correctness')!s:<16}"
    )
    lines.append(
        f"{'process':<12} {left.get('process')!s:<16} {right.get('process')!s:<16}"
    )
    lines.append(
        f"{'efficiency':<12} {left.get('efficiency')!s:<16} {right.get('efficiency')!s:<16}"
    )
    lt = (left.get("retries") or {}).get("total") if (left.get("retries") or {}).get("observed") else "n/a"
    rt = (right.get("retries") or {}).get("total") if (right.get("retries") or {}).get("observed") else "n/a"
    lines.append(f"{'retries':<12} {lt!s:<16} {rt!s:<16}")
    return "\n".join(lines)

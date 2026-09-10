"""Score a bench product against the case oracle. Reads disk only. No LLM."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import yaml

from deltafuse.bench import BenchError
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
    changes = product / "docs" / "changes"
    if not changes.is_dir():
        return None
    pkgs = sorted(p.parent for p in changes.glob("*/change.yaml"))
    return pkgs[0] if pkgs else None


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


def _check(cid: str, ok: bool, detail: str = "") -> dict[str, Any]:
    row: dict[str, Any] = {"id": cid, "pass": bool(ok)}
    if detail:
        row["detail"] = detail
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
    "targeting",
    "target-confirmed",
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
    "targeting",
    "target-confirmed",
    "implementing",
    "implemented",
    "verifying",
    "converged",
    "archived",
}
_AFTER_DECOMPOSE = _AFTER_SPECIFY - {"specified", "specification-proposed"}
_AFTER_DECLARE = {
    "targeting",
    "target-confirmed",
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
    if present is not None and not present["pass"]:
        return {"status": "not-run", "pass": False, "checks": checks, "metrics": metrics}
    passed = all(c["pass"] for c in runnable) if runnable else False
    return {
        "status": "pass" if passed else "fail",
        "pass": passed,
        "checks": checks,
        "metrics": metrics,
    }


def score_intake(product: Path, case: dict[str, Any], change_dir: Path | None) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    status = _status(change_dir)
    checks.append(_check("present", status in _AFTER_INTAKE, "need Change from /intake"))
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
    want = str(case.get("target_capability") or "")
    caps = routing_claim_capabilities(change_dir)
    cap_values = sorted(set(caps.values()))
    checks.append(_check("routing.capability", want in cap_values, f"got {cap_values!r}, want {want!r}"))
    slices = load_slice_records(change_dir)
    matching = [row for row in slices if row.primary_capability == want]
    min_slices = int(case.get("min_slices") or 1)
    checks.append(
        _check(
            "slices.capability",
            len(matching) >= min_slices,
            f"{len(matching)} slices for {want}, need >= {min_slices}",
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
    live = product / str(case.get("live_spec") or "")
    text = live.read_text(encoding="utf-8") if live.is_file() else ""
    missing = [tok for tok in (case.get("spec_must_contain") or []) if tok not in text]
    checks.append(
        _check("live.spec.keywords", not missing, f"missing {missing!r} in {case.get('live_spec')}")
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
    checks.append(_check("tasks.present", bool(task_files), "need at least one TASK"))
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
            "targeting",
            {"targeting", "target-confirmed"},
            _AFTER_DECLARE - {"targeting", "target-confirmed"},
        )
    )
    red_dir = change_dir / "evidence" / "red"
    red_files = list(red_dir.glob("*.yaml")) if red_dir.is_dir() else []
    checks.append(_check("evidence.red", bool(red_files), "need evidence/red"))
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


def run_hidden_suite(product: Path, case: dict[str, Any]) -> tuple[bool, str]:
    hidden_rel = str(case.get("hidden_suite") or "hidden_suite/test_acceptance.py")
    hidden_src = Path(case["dir"]) / hidden_rel
    if not hidden_src.is_file():
        return False, "hidden suite missing from pack"
    src = product / "src"
    if not src.is_dir():
        return False, "product has no src/"
    with tempfile.TemporaryDirectory(prefix="df-bench-hidden-") as tmp:
        tmp_path = Path(tmp)
        shutil.copytree(src, tmp_path / "src")
        tests = tmp_path / "tests"
        tests.mkdir()
        shutil.copy2(hidden_src, tests / hidden_src.name)
        env = os.environ.copy()
        env["PYTHONPATH"] = str(tmp_path / "src")
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", str(tests), "-q", "--tb=line"],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
            env=env,
        )
        out = (proc.stdout or "") + (proc.stderr or "")
        return proc.returncode == 0, out[-800:]


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
    leak = False
    needles = [str(name) for name in (case.get("hidden_tests") or [])]
    tests_dir = product / "tests"
    if tests_dir.is_dir() and needles:
        for path in tests_dir.rglob("*.py"):
            text = path.read_text(encoding="utf-8", errors="ignore")
            if any(needle in text for needle in needles):
                leak = True
                break
    checks.append(_check("hidden.not.in.product", not leak, "hidden tests must not appear in product tests/"))
    hidden_ok, hidden_out = run_hidden_suite(product, case)
    detail = hidden_out.strip()[:400] if reveal_hidden else ("hidden suite failed" if not hidden_ok else "")
    checks.append(_check("hidden.suite", hidden_ok, detail))
    limiter_path = product / "src" / "ratelimit" / "limiter.py"
    limiter = limiter_path.read_text(encoding="utf-8") if limiter_path.is_file() else ""
    checks.append(
        _check("code.penalty_seconds", "penalty_seconds" in limiter, "implementation must accept penalty_seconds")
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
    first_fail = next((name for name in wanted if not stages[name]["pass"]), None)
    return {
        "schema_version": 1,
        "case": case["id"],
        "label": label,
        "change": change_dir.name if change_dir is not None else None,
        "stages": stages,
        "first_fail": first_fail,
        "passed_stages": sum(1 for name in wanted if stages[name]["pass"]),
        "total_stages": len(wanted),
        "pass": first_fail is None,
    }


def format_score(report: dict[str, Any]) -> str:
    header = f"bench {report['case']}"
    if report.get("label"):
        header += f"  label={report['label']}"
    lines = [
        header,
        f"pass={report['pass']}  {report['passed_stages']}/{report['total_stages']}"
        + (f"  first_fail={report['first_fail']}" if report.get("first_fail") else ""),
    ]
    for name, row in report.get("stages", {}).items():
        mark = "PASS" if row.get("pass") else str(row.get("status", "fail")).upper()
        lines.append(f"  {name:<12} {mark}")
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
    lines = [
        f"compare {left.get('case')} vs {right.get('case')}",
        f"{'stage':<12} {l_lab:<12} {r_lab:<12}",
    ]
    for name in names:
        lv = left.get("stages", {}).get(name, {})
        rv = right.get("stages", {}).get(name, {})
        ls = "PASS" if lv.get("pass") else str(lv.get("status", "-"))
        rs = "PASS" if rv.get("pass") else str(rv.get("status", "-"))
        lines.append(f"{name:<12} {ls:<12} {rs:<12}")
    lines.append(
        f"{'total':<12} {left.get('passed_stages')}/{left.get('total_stages'):<8} "
        f"{right.get('passed_stages')}/{right.get('total_stages')}"
    )
    return "\n".join(lines)

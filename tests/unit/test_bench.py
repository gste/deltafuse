from pathlib import Path
import shutil

import yaml

from deltafuse.bench import BenchError
from deltafuse.bench.init_product import format_worker_start_prompt, init_bench_product
from deltafuse.bench.loader import PACK_ENV, list_cases, load_case
from deltafuse.bench.score import compare_reports, run_hidden_suite, score_product
from deltafuse.cli import main
from tests.fixtures.change_builder import MockChangeBuilder

_CAP = "security.ratelimit"
_SPEC_REF = "docs/spec/security/ratelimit.md#REQ-RL-01"
_M02_IMPL = Path(__file__).resolve().parents[1] / "fixtures" / "bench" / "m02_impl" / "src" / "ratelimit"
_US_CAP = "monitoring.usage_stats"
_POL_CAP = "security.rate_policy"
_US_REF = "docs/spec/monitoring/usage_stats.md#REQ-US-01"
_POL_REF = "docs/spec/security/rate_policy.md#REQ-RP-01"

_PENALTY_LIMITER = '''from __future__ import annotations

import time


class TokenBucketLimiter:
    def __init__(self, capacity: float, refill_rate: float, penalty_seconds: float = 0.0) -> None:
        if capacity <= 0 or refill_rate < 0 or penalty_seconds < 0:
            raise ValueError("invalid limiter parameters")
        self.capacity = float(capacity)
        self.refill_rate = float(refill_rate)
        self.penalty_seconds = float(penalty_seconds)
        self._buckets: dict[str, tuple[float, float]] = {}
        self._blocked_until: dict[str, float] = {}

    def _refill(self, key: str) -> tuple[float, float]:
        now = time.monotonic()
        tokens, last = self._buckets.get(key, (self.capacity, now))
        tokens = min(self.capacity, tokens + (now - last) * self.refill_rate)
        self._buckets[key] = (tokens, now)
        return self._buckets[key]

    def consume(self, key: str, tokens: float) -> bool:
        now = time.monotonic()
        until = self._blocked_until.get(key, 0.0)
        if until > now:
            return False
        current, ts = self._refill(key)
        if current >= tokens:
            self._buckets[key] = (current - tokens, ts)
            return True
        if self.penalty_seconds > 0:
            self._blocked_until[key] = now + self.penalty_seconds
        return False

    def is_blocked(self, key: str) -> bool:
        return self._blocked_until.get(key, 0.0) > time.monotonic()
'''


def _rewire_m01(product: Path, builder: MockChangeBuilder, *, add_penalty_keyword: bool = True) -> None:
    for path in (builder.change_dir / "slices").glob("*.md"):
        text = path.read_text(encoding="utf-8")
        path.write_text(
            text.replace("system.core", _CAP).replace("docs/spec/core.md#REQ-01", _SPEC_REF),
            encoding="utf-8",
        )
    routing_path = builder.change_dir / "routing.yaml"
    routing = yaml.safe_load(routing_path.read_text(encoding="utf-8"))
    for row in routing["claims"].values():
        row["primary_capability"] = _CAP
    routing_path.write_text(yaml.safe_dump(routing), encoding="utf-8")
    cov_path = builder.change_dir / "coverage.yaml"
    cov = yaml.safe_load(cov_path.read_text(encoding="utf-8"))
    for row in cov.get("claims", {}).values():
        row["spec_refs"] = [_SPEC_REF]
    cov_path.write_text(yaml.safe_dump(cov), encoding="utf-8")
    spec_delta = (
        "---\n"
        f"change: {builder.change_id}\n"
        "status: proposed\n"
        "slices: [SLICE-01]\n"
        "added: []\n"
        f"modified: [{_SPEC_REF}]\n"
        "removed: []\n"
        "---\n"
    )
    (builder.change_dir / "spec-delta.md").write_text(spec_delta, encoding="utf-8")
    if add_penalty_keyword:
        spec = product / "docs" / "spec" / "security" / "ratelimit.md"
        text = spec.read_text(encoding="utf-8")
        if "penalty_seconds" not in text:
            spec.write_text(text + "\n## REQ-RL-05 Penalty\n\npenalty_seconds MUST default to 0.0.\n", encoding="utf-8")


def _copy_coverage_evidence(builder: MockChangeBuilder) -> None:
    cov_path = builder.change_dir / "coverage.yaml"
    cov = yaml.safe_load(cov_path.read_text(encoding="utf-8"))
    template = next((row for row in cov.get("claims", {}).values() if row.get("evidence")), None)
    if template is None:
        return
    for row in cov["claims"].values():
        row["evidence"] = dict(template.get("evidence") or {})
        row["status"] = template.get("status", row.get("status"))
        row["tasks"] = list(template.get("tasks") or row.get("tasks") or [])
    cov_path.write_text(yaml.safe_dump(cov), encoding="utf-8")


def _score(product: Path, repo_root: Path, **kwargs):
    return score_product(product, pack_root=repo_root, **kwargs)


def test_list_and_load_m01():
    assert "M01-cooldown" in list_cases()
    assert "M02-policy-stats" in list_cases()
    case = load_case("M01-cooldown")
    assert case["target_capability"] == "security.ratelimit"
    assert (case["dir"] / "oracle.yaml").is_file()
    assert (case["dir"] / "hidden_suite" / "test_acceptance.py").is_file()


def test_init_does_not_copy_oracle(tmp_path: Path, repo_root: Path):
    product = tmp_path / "m01"
    init_bench_product("M01-cooldown", product, framework_root=repo_root)
    assert (product / ".deltafuse" / "bench.yaml").is_file()
    assert (product / "docs" / "intake" / "M01-cooldown.md").is_file()
    assert (product / "src" / "ratelimit" / "limiter.py").is_file()
    assert (product / "BENCH.md").is_file()
    tree = "\n".join(p.as_posix() for p in product.rglob("*") if p.is_file())
    assert "oracle.yaml" not in tree
    assert "hidden_suite" not in tree
    assert "penalty_lockout_and_expiration" not in (product / "tests" / "test_limiter.py").read_text(
        encoding="utf-8"
    )
    limiter = (product / "src" / "ratelimit" / "limiter.py").read_text(encoding="utf-8")
    assert "penalty_seconds" not in limiter
    bench_md = (product / "BENCH.md").read_text(encoding="utf-8")
    do_section = bench_md.split("## Do not")[0]
    assert "bench score" not in do_section
    forbidden = bench_md.split("## Do not", 1)[1]
    assert "outside this project" in forbidden.lower()
    assert "oracle" not in forbidden.lower()
    assert "hidden" not in forbidden.lower()
    meta = yaml.safe_load((product / ".deltafuse" / "bench.yaml").read_text(encoding="utf-8"))
    assert "pack" not in meta
    assert meta["case"] == "M01-cooldown"


def test_score_init_is_not_run(tmp_path: Path, repo_root: Path):
    product = tmp_path / "m01"
    init_bench_product("M01-cooldown", product, framework_root=repo_root)
    report = _score(product, repo_root)
    assert report["pass"] is False
    assert report["first_fail"] == "intake"
    assert report["stages"]["intake"]["status"] == "not-run"
    assert report["stages"]["specify"]["status"] == "not-run"


def test_specify_requires_penalty_in_live_spec(tmp_path: Path, repo_root: Path):
    product = tmp_path / "m01"
    init_bench_product("M01-cooldown", product, framework_root=repo_root)
    builder = (
        MockChangeBuilder(product, change_id="CHG-080", title="Penalty")
        .step_intake(claims=["CR-001", "CR-002", "CR-003"])
        .step_analyze()
        .step_specify()
    )
    _rewire_m01(product, builder, add_penalty_keyword=False)
    report = _score(product, repo_root, stage="specify")
    assert report["stages"]["specify"]["pass"] is False
    assert any(c["id"] == "live.spec.penalty_seconds" and not c["pass"] for c in report["stages"]["specify"]["checks"])

    spec = product / "docs" / "spec" / "security" / "ratelimit.md"
    spec.write_text(spec.read_text(encoding="utf-8") + "\npenalty_seconds MUST default to 0.0.\n", encoding="utf-8")
    again = _score(product, repo_root, stage="specify")
    assert any(c["id"] == "live.spec.penalty_seconds" and c["pass"] for c in again["stages"]["specify"]["checks"])


def test_hidden_suite_fails_on_seed_limiter(tmp_path: Path, repo_root: Path):
    product = tmp_path / "m01"
    init_bench_product("M01-cooldown", product, framework_root=repo_root)
    case = load_case("M01-cooldown")
    ok, _ = run_hidden_suite(product, case)
    assert ok is False


def test_hidden_suite_passes_with_penalty(tmp_path: Path, repo_root: Path):
    product = tmp_path / "m01"
    init_bench_product("M01-cooldown", product, framework_root=repo_root)
    (product / "src" / "ratelimit" / "limiter.py").write_text(_PENALTY_LIMITER, encoding="utf-8")
    case = load_case("M01-cooldown")
    ok, out = run_hidden_suite(product, case)
    assert ok is True, out


def test_full_synthetic_package_passes(tmp_path: Path, repo_root: Path):
    product = tmp_path / "m01"
    init_bench_product("M01-cooldown", product, framework_root=repo_root)
    builder = (
        MockChangeBuilder(product, change_id="CHG-081", title="Penalty")
        .step_intake(claims=["CR-001", "CR-002", "CR-003"])
        .step_analyze()
        .step_specify()
    )
    _rewire_m01(product, builder)
    (product / "src" / "ratelimit" / "limiter.py").write_text(_PENALTY_LIMITER, encoding="utf-8")
    builder.step_decompose().step_declare().step_implement().step_verify()
    _copy_coverage_evidence(builder)
    report = _score(product, repo_root, label="fixture")
    assert report["pass"] is True, report
    assert report["passed_stages"] == 7
    assert report["first_fail"] is None
    assert report["correctness"] == 100.0
    assert report["score"] is None
    assert report["score_reason"] == "no_retry_journal"
    assert report["points_max"] > 0
    assert report["retries"]["observed"] is False
    assert all(row["pass"] for row in report["stages"].values())
    already_past = [
        check["id"]
        for row in report["stages"].values()
        for check in row.get("checks") or []
        if check.get("detail") == "already past this gate"
    ]
    assert already_past, "finished Change still lists past gates; they must not be the headline"


def test_compare_table():
    left = {
        "case": "M01-cooldown",
        "label": "opus",
        "score": 86.0,
        "correctness": 100.0,
        "process": 65.0,
        "efficiency": 80.0,
        "retries": {"observed": True, "total": 2},
        "stages": {
            "specify": {"pass": True, "check_rate": 1.0, "gate_retries": 0},
            "implement": {"pass": True, "check_rate": 1.0, "gate_retries": 2},
        },
    }
    right = {
        "case": "M01-cooldown",
        "label": "flash",
        "score": 52.0,
        "correctness": 71.2,
        "process": 40.0,
        "efficiency": 40.0,
        "retries": {"observed": True, "total": 15},
        "stages": {
            "specify": {"pass": True, "check_rate": 1.0, "gate_retries": 1, "status": "pass"},
            "implement": {"pass": False, "check_rate": 0.4, "gate_retries": 4, "status": "fail"},
        },
    }
    text = compare_reports(left, right)
    assert "opus" in text and "flash" in text
    assert "implement" in text
    assert "correctness" in text
    assert "score" in text
    assert "retries" in text


def test_bench_cli_init_prints_worker_prompt(tmp_path: Path, repo_root: Path, capsys, monkeypatch):
    monkeypatch.chdir(repo_root)
    product = tmp_path / "cli-m01"
    assert main(["bench", "init", "M01-cooldown", str(product)]) == 0
    out, _ = capsys.readouterr()
    assert "paste into the Worker" in out
    assert "deltafuse next" in out
    assert "docs/intake/M01-cooldown.md" in out
    assert "bench score" not in out
    prompt = format_worker_start_prompt({"intake": "docs/intake/M01-cooldown.md"})
    assert prompt in out
    assert "bench score" not in prompt


def test_bench_cli_init_and_score_json(tmp_path: Path, repo_root: Path, capsys, monkeypatch):
    monkeypatch.chdir(repo_root)
    product = tmp_path / "cli-m01"
    assert main(["bench", "init", "M01-cooldown", str(product)]) == 0
    capsys.readouterr()
    ret = main(["bench", "score", str(product), "--pack", str(repo_root), "--json", "--label", "smoke"])
    out, _ = capsys.readouterr()
    assert ret == 1
    assert '"case": "M01-cooldown"' in out
    assert '"label": "smoke"' in out
    assert '"first_fail": "intake"' in out


def test_bench_cli_compare(tmp_path: Path, capsys):
    left = tmp_path / "opus.json"
    right = tmp_path / "flash.json"
    left.write_text(
        '{"case":"M01-cooldown","label":"opus","passed_stages":7,"total_stages":7,'
        '"stages":{"specify":{"pass":true},"implement":{"pass":true}}}\n',
        encoding="utf-8",
    )
    right.write_text(
        '{"case":"M01-cooldown","label":"flash","passed_stages":3,"total_stages":7,'
        '"stages":{"specify":{"pass":true},"implement":{"pass":false,"status":"fail"}}}\n',
        encoding="utf-8",
    )
    assert main(["bench", "compare", str(left), str(right)]) == 0
    out, _ = capsys.readouterr()
    assert "opus" in out and "flash" in out
    assert "implement" in out


def test_score_requires_pack(tmp_path: Path, repo_root: Path, monkeypatch):
    monkeypatch.delenv(PACK_ENV, raising=False)
    product = tmp_path / "m01"
    init_bench_product("M01-cooldown", product, framework_root=repo_root, pack_root=repo_root)
    try:
        score_product(product)
    except BenchError as ex:
        assert "Judge pack required" in str(ex)
    else:
        raise AssertionError("expected BenchError")


def test_score_rejects_oracle_in_sandbox(tmp_path: Path, repo_root: Path):
    product = tmp_path / "m01"
    init_bench_product("M01-cooldown", product, framework_root=repo_root, pack_root=repo_root)
    (product / "oracle.yaml").write_text("leaked: true\n", encoding="utf-8")
    try:
        _score(product, repo_root)
    except BenchError as ex:
        assert "judge files" in str(ex)
    else:
        raise AssertionError("expected BenchError")


def test_score_refuses_out_file_in_sandbox(tmp_path: Path, repo_root: Path, monkeypatch):
    monkeypatch.chdir(repo_root)
    product = tmp_path / "m01"
    init_bench_product("M01-cooldown", product, framework_root=repo_root, pack_root=repo_root)
    inside = product / "opus.json"
    ret = main(
        [
            "bench",
            "score",
            str(product),
            "--pack",
            str(repo_root),
            "--json",
            "--out-file",
            str(inside),
        ]
    )
    assert ret == 2
    assert not inside.is_file()


def test_hidden_suite_failure_is_redacted(tmp_path: Path, repo_root: Path):
    product = tmp_path / "m01"
    init_bench_product("M01-cooldown", product, framework_root=repo_root, pack_root=repo_root)
    (
        MockChangeBuilder(product, change_id="CHG-082", title="Penalty")
        .step_intake(claims=["CR-001", "CR-002", "CR-003"])
        .step_analyze()
        .step_specify()
        .step_decompose()
        .step_declare()
        .step_implement()
    )
    report = _score(product, repo_root, stage="implement")
    hidden = [c for c in report["stages"]["implement"]["checks"] if str(c["id"]).startswith("hidden.suite")]
    assert hidden
    failed = [c for c in hidden if not c["pass"]]
    assert failed, "seed limiter must fail lockout/isolation"
    assert all(c.get("detail") == "hidden suite failed" for c in failed)
    assert all("AssertionError" not in (c.get("detail") or "") for c in hidden)
    assert any(c["id"].endswith("test_backward_compatibility") and c["pass"] for c in hidden)
    assert report["correctness"] < 50.0
    assert report["score"] is None

    revealed = _score(product, repo_root, stage="implement", reveal_hidden=True)
    shown_failed = [
        c
        for c in revealed["stages"]["implement"]["checks"]
        if str(c["id"]).startswith("hidden.suite") and not c["pass"]
    ]
    assert shown_failed
    assert any(c.get("detail") and c["detail"] != "hidden suite failed" for c in shown_failed)


def test_journal_retries_feed_process_score(tmp_path: Path, repo_root: Path):
    from deltafuse.bench.journal import record_event

    product = tmp_path / "m01"
    init_bench_product("M01-cooldown", product, framework_root=repo_root, pack_root=repo_root)
    record_event(product, cmd="check-gate", gate="intake", ok=False)
    record_event(product, cmd="check-gate", gate="intake", ok=False)
    record_event(product, cmd="check-gate", gate="intake", ok=True)
    record_event(product, cmd="evidence", phase="red", ok=False)
    report = _score(product, repo_root)
    assert report["retries"]["observed"] is True
    assert report["retries"]["check_gate"] == 2
    assert report["retries"]["gate_attempts"] == 3
    assert report["retries"]["evidence"] == 1
    assert report["retries"]["total"] == 3
    assert report["process"] == round(100.0 * 1 / 3, 1)
    assert report["stages"]["intake"]["gate_retries"] == 2
    assert report["stages"]["intake"]["gate_attempts"] == 3
    assert report["efficiency"] == round(report["correctness"] * report["process"] / 100.0, 1)
    assert report["score"] == round(0.6 * report["correctness"] + 0.4 * report["process"], 1)


def test_check_gate_cli_appends_journal(tmp_path: Path, repo_root: Path):
    from deltafuse.bench.journal import load_events

    product = tmp_path / "m01"
    init_bench_product("M01-cooldown", product, framework_root=repo_root, pack_root=repo_root)
    builder = MockChangeBuilder(product, change_id="CHG-090", title="Penalty").step_intake(
        claims=["CR-001", "CR-002", "CR-003"]
    )
    ret = main(["check-gate", str(builder.change_dir), "--gate", "intake"])
    assert ret == 0
    events = load_events(product)
    assert events
    assert events[-1]["cmd"] == "check-gate"
    assert events[-1]["gate"] == "intake"
    assert events[-1]["ok"] is True


def _install_m02_impl(product: Path) -> None:
    dest = product / "src" / "ratelimit"
    dest.mkdir(parents=True, exist_ok=True)
    for name in ("limiter.py", "stats.py", "policy.py", "__init__.py"):
        shutil.copy2(_M02_IMPL / name, dest / name)


def _write_m02_live_specs(product: Path) -> None:
    usage = product / "docs" / "spec" / "monitoring" / "usage_stats.md"
    usage.parent.mkdir(parents=True, exist_ok=True)
    usage.write_text(
        "# monitoring.usage_stats\n\n"
        "## REQ-US-01 get_stats\n\n"
        "get_stats(key) MUST return total_calls, successful_calls, rejected_calls,\n"
        "peak_rate, token_rejects, policy_rejects, and blocked_until.\n",
        encoding="utf-8",
    )
    policy = product / "docs" / "spec" / "security" / "rate_policy.md"
    policy.write_text(
        "# security.rate_policy\n\n"
        "## REQ-RP-01 consecutive rejects\n\n"
        "reject_threshold consecutive failed consume calls MUST set blocked_until\n"
        "for block_seconds. Tokens MUST NOT debit while blocked.\n",
        encoding="utf-8",
    )


def _rewire_m02(product: Path, builder: MockChangeBuilder, *, add_live_specs: bool = True) -> None:
    mapping = {"SLICE-01": (_US_CAP, _US_REF), "SLICE-02": (_POL_CAP, _POL_REF)}
    for path in (builder.change_dir / "slices").glob("*.md"):
        cap, ref = mapping.get(path.stem, (_US_CAP, _US_REF))
        text = path.read_text(encoding="utf-8")
        path.write_text(
            text.replace("system.core", cap).replace("docs/spec/core.md#REQ-01", ref),
            encoding="utf-8",
        )
    routing_path = builder.change_dir / "routing.yaml"
    routing = yaml.safe_load(routing_path.read_text(encoding="utf-8"))
    claims = list(routing["claims"])
    for index, cid in enumerate(claims):
        routing["claims"][cid]["primary_capability"] = _US_CAP if index % 2 == 0 else _POL_CAP
    routing_path.write_text(yaml.safe_dump(routing), encoding="utf-8")
    cov_path = builder.change_dir / "coverage.yaml"
    cov = yaml.safe_load(cov_path.read_text(encoding="utf-8"))
    for index, cid in enumerate(cov.get("claims", {})):
        slice_id = "SLICE-01" if index % 2 == 0 else "SLICE-02"
        ref = _US_REF if slice_id == "SLICE-01" else _POL_REF
        cov["claims"][cid]["slice"] = slice_id
        cov["claims"][cid]["spec_refs"] = [ref]
    cov_path.write_text(yaml.safe_dump(cov), encoding="utf-8")
    spec_delta = (
        "---\n"
        f"change: {builder.change_id}\n"
        "status: proposed\n"
        "slices: [SLICE-01, SLICE-02]\n"
        f"added: [{_US_REF}, {_POL_REF}]\n"
        "modified: []\n"
        "removed: []\n"
        "---\n"
    )
    (builder.change_dir / "spec-delta.md").write_text(spec_delta, encoding="utf-8")
    catalog_path = product / "docs" / "spec" / "_capabilities.yaml"
    catalog = yaml.safe_load(catalog_path.read_text(encoding="utf-8"))
    domains = catalog.setdefault("domains", {})
    security = domains.setdefault("security", {"summary": "Security controls", "capabilities": {}})
    security.setdefault("capabilities", {})["rate_policy"] = {
        "summary": "Consecutive reject policy",
        "spec": ["docs/spec/security/rate_policy.md"],
    }
    domains["monitoring"] = {
        "summary": "Usage telemetry",
        "capabilities": {
            "usage_stats": {
                "summary": "Per-key consume statistics",
                "spec": ["docs/spec/monitoring/usage_stats.md"],
            }
        },
    }
    catalog_path.write_text(yaml.safe_dump(catalog, sort_keys=False), encoding="utf-8")
    if add_live_specs:
        _write_m02_live_specs(product)


def test_m02_init_keeps_oracle_off_disk(tmp_path: Path, repo_root: Path):
    product = tmp_path / "m02"
    init_bench_product("M02-policy-stats", product, framework_root=repo_root)
    tree = "\n".join(p.as_posix() for p in product.rglob("*") if p.is_file())
    assert "oracle.yaml" not in tree
    assert "hidden_suite" not in tree
    assert not (product / "docs" / "spec" / "monitoring" / "usage_stats.md").is_file()
    assert not (product / "docs" / "spec" / "security" / "rate_policy.md").is_file()
    limiter = (product / "src" / "ratelimit" / "limiter.py").read_text(encoding="utf-8")
    assert "get_stats" not in limiter
    assert "redis" not in limiter.lower()


def test_m02_specify_requires_both_live_specs(tmp_path: Path, repo_root: Path):
    product = tmp_path / "m02"
    init_bench_product("M02-policy-stats", product, framework_root=repo_root)
    builder = (
        MockChangeBuilder(product, change_id="CHG-201", title="Stats policy")
        .step_intake(claims=["CR-001", "CR-002", "CR-003"])
        .step_analyze(slices=["SLICE-01", "SLICE-02"])
        .step_specify()
    )
    _rewire_m02(product, builder, add_live_specs=False)
    report = _score(product, repo_root, stage="specify")
    assert report["stages"]["specify"]["pass"] is False
    ids = [c["id"] for c in report["stages"]["specify"]["checks"] if not c["pass"]]
    assert any(cid.startswith("live.spec.usage_stats") for cid in ids)
    assert any(cid.startswith("live.spec.rate_policy") for cid in ids)

    _write_m02_live_specs(product)
    again = _score(product, repo_root, stage="specify")
    assert any(
        c["id"].startswith("live.spec.usage_stats") and c["pass"]
        for c in again["stages"]["specify"]["checks"]
    )
    assert any(
        c["id"].startswith("live.spec.rate_policy") and c["pass"]
        for c in again["stages"]["specify"]["checks"]
    )


def test_m02_hidden_suite_fails_on_seed(tmp_path: Path, repo_root: Path):
    product = tmp_path / "m02"
    init_bench_product("M02-policy-stats", product, framework_root=repo_root)
    case = load_case("M02-policy-stats")
    ok, _ = run_hidden_suite(product, case)
    assert ok is False


def test_m02_hidden_suite_passes_with_fixture(tmp_path: Path, repo_root: Path):
    product = tmp_path / "m02"
    init_bench_product("M02-policy-stats", product, framework_root=repo_root)
    _install_m02_impl(product)
    case = load_case("M02-policy-stats")
    ok, out = run_hidden_suite(product, case)
    assert ok is True, out


def test_m02_full_synthetic_package_passes(tmp_path: Path, repo_root: Path):
    product = tmp_path / "m02"
    init_bench_product("M02-policy-stats", product, framework_root=repo_root)
    builder = (
        MockChangeBuilder(product, change_id="CHG-202", title="Stats policy")
        .step_intake(claims=["CR-001", "CR-002", "CR-003"])
        .step_analyze(slices=["SLICE-01", "SLICE-02"])
        .step_specify()
    )
    _rewire_m02(product, builder)
    _install_m02_impl(product)
    builder.step_decompose(
        tasks=[
            {
                "id": "TASK-001",
                "slice": "SLICE-01",
                "depends_on": [],
                "allowed_paths": ["src/ratelimit/stats.py"],
            },
            {
                "id": "TASK-002",
                "slice": "SLICE-02",
                "depends_on": [],
                "allowed_paths": ["src/ratelimit/policy.py"],
            },
        ]
    ).step_declare().step_implement().step_verify()
    _copy_coverage_evidence(builder)
    report = _score(product, repo_root, label="fixture")
    assert report["pass"] is True, report
    assert report["passed_stages"] == 7
    assert report["correctness"] == 100.0
    assert report["score"] is None
    assert report["stages"]["analyze"]["metrics"]["slice_count"] >= 2


def test_m02_redis_in_src_is_forbidden(tmp_path: Path, repo_root: Path):
    product = tmp_path / "m02"
    init_bench_product("M02-policy-stats", product, framework_root=repo_root)
    builder = (
        MockChangeBuilder(product, change_id="CHG-203", title="Stats policy")
        .step_intake(claims=["CR-001", "CR-002", "CR-003"])
        .step_analyze(slices=["SLICE-01", "SLICE-02"])
        .step_specify()
        .step_decompose()
        .step_declare()
        .step_implement()
    )
    _rewire_m02(product, builder)
    _install_m02_impl(product)
    limiter = product / "src" / "ratelimit" / "limiter.py"
    limiter.write_text(limiter.read_text(encoding="utf-8") + "\nREDIS = 'redis://localhost'\n", encoding="utf-8")
    report = _score(product, repo_root, stage="implement")
    forbidden = next(c for c in report["stages"]["implement"]["checks"] if c["id"] == "code.forbidden.redis")
    assert forbidden["pass"] is False
    assert report["correctness"] < 100.0



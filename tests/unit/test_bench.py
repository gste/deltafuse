from pathlib import Path

import yaml

from deltafuse.bench.init_product import init_bench_product
from deltafuse.bench.loader import list_cases, load_case
from deltafuse.bench.score import compare_reports, run_hidden_suite, score_product
from deltafuse.cli import main
from tests.fixtures.change_builder import MockChangeBuilder

_CAP = "security.ratelimit"
_SPEC_REF = "docs/spec/security/ratelimit.md#REQ-RL-01"

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


def test_list_and_load_m01():
    assert "M01-cooldown" in list_cases()
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


def test_score_init_is_not_run(tmp_path: Path, repo_root: Path):
    product = tmp_path / "m01"
    init_bench_product("M01-cooldown", product, framework_root=repo_root)
    report = score_product(product)
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
    report = score_product(product, stage="specify")
    assert report["stages"]["specify"]["pass"] is False
    assert any(c["id"] == "live.spec.keywords" and not c["pass"] for c in report["stages"]["specify"]["checks"])

    spec = product / "docs" / "spec" / "security" / "ratelimit.md"
    spec.write_text(spec.read_text(encoding="utf-8") + "\npenalty_seconds MUST default to 0.0.\n", encoding="utf-8")
    again = score_product(product, stage="specify")
    assert any(c["id"] == "live.spec.keywords" and c["pass"] for c in again["stages"]["specify"]["checks"])


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
    report = score_product(product, label="fixture")
    assert report["pass"] is True, report
    assert report["passed_stages"] == 7
    assert report["first_fail"] is None
    assert all(row["pass"] for row in report["stages"].values())


def test_compare_table():
    left = {
        "case": "M01-cooldown",
        "label": "opus",
        "passed_stages": 7,
        "total_stages": 7,
        "stages": {"specify": {"pass": True}, "implement": {"pass": True}},
    }
    right = {
        "case": "M01-cooldown",
        "label": "flash",
        "passed_stages": 3,
        "total_stages": 7,
        "stages": {"specify": {"pass": True, "status": "pass"}, "implement": {"pass": False, "status": "fail"}},
    }
    text = compare_reports(left, right)
    assert "opus" in text and "flash" in text
    assert "implement" in text


def test_bench_cli_init_and_score_json(tmp_path: Path, repo_root: Path, capsys, monkeypatch):
    monkeypatch.chdir(repo_root)
    product = tmp_path / "cli-m01"
    assert main(["bench", "init", "M01-cooldown", str(product)]) == 0
    capsys.readouterr()
    ret = main(["bench", "score", str(product), "--json", "--label", "smoke"])
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

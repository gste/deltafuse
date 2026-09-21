"""Q0-3: the qualification runner's pure parts. No network, no Worker call."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, "scripts")

import qualify  # noqa: E402


_CAMPAIGN_ENV = (
    "DELTAFUSE_TOKENIZER_REQUIRED",
    "DELTAFUSE_TOKENIZE_URL",
    "OPENROUTER_API_KEY",
)


@pytest.fixture(autouse=True)
def _isolate_tokenizer_env():
    """`preflight` sets DELTAFUSE_TOKENIZER_REQUIRED on purpose; keep it in-test.

    monkeypatch only undoes what it set itself, so a variable the code under
    test creates would survive the test. Leaking this one turns every later
    token count in the session into a refusal.
    """
    saved = {name: qualify.os.environ.get(name) for name in _CAMPAIGN_ENV}
    for name in _CAMPAIGN_ENV:
        qualify.os.environ.pop(name, None)
    try:
        yield
    finally:
        for name, value in saved.items():
            if value is None:
                qualify.os.environ.pop(name, None)
            else:
                qualify.os.environ[name] = value


DOC = """# thresholds

prose

<!-- deltafuse:thresholds -->

```yaml
schema_version: 1
campaign:
  runs_per_case: 3
thresholds:
  - id: T1
    metric: correctness_failed_checks
    op: eq
    value: 0
    gating: true
    scope: [per_run, median]
  - id: T9
    metric: under_routing_rate
    op: eq
    value: 0.0
    gating: false
    scope: [per_run]
```
"""


def _doc(tmp_path: Path, text: str = DOC) -> Path:
    path = tmp_path / "thresholds.md"
    path.write_text(text, encoding="utf-8")
    return path


# --- loading --------------------------------------------------------------


def test_load_thresholds_reads_the_marked_block(tmp_path: Path):
    data = qualify.load_thresholds(_doc(tmp_path))
    assert [row["id"] for row in data["thresholds"]] == ["T1", "T9"]
    assert data["campaign"]["runs_per_case"] == 3
    assert len(data["revision"]) == 8


def test_revision_changes_with_the_block(tmp_path: Path):
    first = qualify.load_thresholds(_doc(tmp_path))["revision"]
    second = qualify.load_thresholds(
        _doc(tmp_path, DOC.replace("value: 0\n    gating: true", "value: 1\n    gating: true"))
    )["revision"]
    assert first != second


def test_load_thresholds_requires_the_marker(tmp_path: Path):
    with pytest.raises(qualify.QualificationError):
        qualify.load_thresholds(_doc(tmp_path, "# nothing here\n"))


def test_load_thresholds_rejects_unknown_op(tmp_path: Path):
    broken = DOC.replace("op: eq", "op: approximately", 1)
    with pytest.raises(qualify.QualificationError):
        qualify.load_thresholds(_doc(tmp_path, broken))


# --- evaluation -----------------------------------------------------------


def test_gating_violation_is_a_failure(tmp_path: Path):
    data = qualify.load_thresholds(_doc(tmp_path))
    failures, observed = qualify.evaluate(
        data, {"correctness_failed_checks": 2, "under_routing_rate": 0.0}, "per_run"
    )
    assert failures and "T1" in failures[0]
    assert observed == []


def test_non_gating_violation_is_only_observed(tmp_path: Path):
    data = qualify.load_thresholds(_doc(tmp_path))
    failures, observed = qualify.evaluate(
        data, {"correctness_failed_checks": 0, "under_routing_rate": 0.4}, "per_run"
    )
    assert failures == []
    assert observed and "T9" in observed[0]


def test_unmeasured_gating_metric_is_a_failure_not_a_pass(tmp_path: Path):
    """Rule 3 of thresholds.md: a missing measurement never passes implicitly."""
    data = qualify.load_thresholds(_doc(tmp_path))
    failures, _ = qualify.evaluate(data, {"correctness_failed_checks": None}, "per_run")
    assert failures == ["T1 correctness_failed_checks: not measured"]


def test_scope_selects_which_thresholds_apply(tmp_path: Path):
    data = qualify.load_thresholds(_doc(tmp_path))
    failures, observed = qualify.evaluate(data, {"correctness_failed_checks": 0}, "median")
    assert failures == []
    assert observed == []  # T9 is per_run only


# --- medians --------------------------------------------------------------


def test_median_metrics_over_runs():
    runs = [
        {"metrics": {"gate_retries_total": 1}},
        {"metrics": {"gate_retries_total": 5}},
        {"metrics": {"gate_retries_total": 2}},
    ]
    assert qualify.median_metrics(runs)["gate_retries_total"] == 2


def test_median_is_unmeasured_when_any_run_is():
    runs = [{"metrics": {"context_peak_tokens": 10}}, {"metrics": {"context_peak_tokens": None}}]
    assert qualify.median_metrics(runs)["context_peak_tokens"] is None


# --- hallucinated paths (T6) ---------------------------------------------


class _FakeSandbox:
    def __init__(self, root: Path) -> None:
        self.root = root

    def resolve(self, rel: str):
        return qualify.Sandbox.resolve(self, rel)  # type: ignore[arg-type]


def test_hallucinated_argv_paths(tmp_path: Path):
    real = tmp_path / "tests" / "test_real.py"
    real.parent.mkdir(parents=True)
    real.write_text("", encoding="utf-8")
    sandbox = _FakeSandbox(tmp_path)
    found = qualify.hallucinated_argv_paths(
        ["pytest", "tests/test_real.py", "tests/test_missing.py", "-q"], sandbox
    )
    assert found == ["tests/test_missing.py"]


def test_subcommand_names_are_not_paths(tmp_path: Path):
    sandbox = _FakeSandbox(tmp_path)
    assert qualify.hallucinated_argv_paths(["deltafuse", "next", "--json"], sandbox) == []


# --- fail-closed preflight ------------------------------------------------


def test_preflight_blocks_without_tokenizer(monkeypatch):
    monkeypatch.delenv("DELTAFUSE_TOKENIZE_URL", raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    _, blockers = qualify.preflight("qwen/qwen3.8-27b", live=True)
    assert any("DELTAFUSE_TOKENIZE_URL" in b for b in blockers)


def test_preflight_blocks_without_api_key(monkeypatch):
    monkeypatch.setenv("DELTAFUSE_TOKENIZE_URL", "http://127.0.0.1:1240/tokenize")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    _, blockers = qualify.preflight("qwen/qwen3.8-27b", live=True)
    assert any("OPENROUTER_API_KEY" in b for b in blockers)


def test_preflight_blocks_on_a_silent_tokenizer(monkeypatch):
    """A configured URL is not a working tokenizer: the probe must answer."""
    monkeypatch.setenv("DELTAFUSE_TOKENIZE_URL", "http://127.0.0.1:1240/tokenize")
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    monkeypatch.setattr("urllib.request.urlopen", _refuse)
    _, blockers = qualify.preflight("qwen/qwen3.8-27b", live=True)
    assert any("did not answer a probe" in b for b in blockers)


def _refuse(*args, **kwargs):
    raise OSError("connection refused")


def test_preflight_requires_a_measured_tokenizer(monkeypatch):
    monkeypatch.setenv("DELTAFUSE_TOKENIZE_URL", "http://127.0.0.1:1240/tokenize")
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    monkeypatch.setattr(qualify, "probe_tokenizer", lambda: None)
    key, blockers = qualify.preflight("qwen/qwen3.8-27b", live=True)
    assert key == "k"
    assert blockers == []
    assert qualify.os.environ["DELTAFUSE_TOKENIZER_REQUIRED"] == "1"


def test_dry_run_exits_pending_without_environment(monkeypatch, capsys):
    monkeypatch.delenv("DELTAFUSE_TOKENIZE_URL", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    code = qualify.main(["--cases", "M01-cooldown", "--dry-run"])
    assert code == qualify.EXIT_PENDING


# --- the shipped document -------------------------------------------------


def test_shipped_thresholds_parse():
    data = qualify.load_thresholds()
    ids = [row["id"] for row in data["thresholds"]]
    assert {"T1", "T2", "T3", "T4", "T5", "T6", "T7", "T8", "T9", "T10"} <= set(ids)


def test_shipped_budget_matches_the_contract():
    reference = qualify.load_thresholds()["reference"]
    assert reference["framework_input_tokens"] == 64000
    assert reference["framework_input_files"] == 24
    assert reference["qualification_window_tokens"] == 131072


def test_new_observables_are_not_gating_yet():
    """T9/T10 gate only once the mechanism that produces them exists."""
    rows = {row["id"]: row for row in qualify.load_thresholds()["thresholds"]}
    assert rows["T9"]["gating"] is False
    assert rows["T10"]["gating"] is False
    assert rows["T9"]["gating_blocked_by"]
    assert rows["T10"]["gating_blocked_by"]


def test_every_shipped_metric_is_produced_by_the_runner():
    """Drift guard: renaming a metric in the doc without the runner is a bug."""
    produced = set(
        qualify.collect_metrics(
            {"stages": {}, "retries": {}, "defense_checks": {}}, qualify.RunTrace()
        )
    )
    declared = {row["metric"] for row in qualify.load_thresholds()["thresholds"]}
    assert declared <= produced, f"not produced: {sorted(declared - produced)}"


# --- regressions from the first live diagnostic run (2026-09-21) ----------


def test_git_revision_path_is_not_hallucinated(tmp_path: Path):
    sandbox = _FakeSandbox(tmp_path)
    argv = ["git", "show", "HEAD:docs/changes/CHG-001/change.yaml"]
    assert qualify.hallucinated_argv_paths(argv, sandbox) == []


def test_worker_cannot_click_a_human_gate(tmp_path: Path):
    sandbox = _FakeSandbox(tmp_path)
    trace = qualify.RunTrace()
    out = qualify.execute_tool(
        "run", {"argv": ["deltafuse", "decide", ".", "--spec", "--status", "accepted"]},
        sandbox, trace,  # type: ignore[arg-type]
    )
    assert out.startswith("refused")
    assert trace.gate_attempts == ["deltafuse decide . --spec --status accepted"]


def test_hallucinated_reads_are_counted_once(tmp_path: Path):
    sandbox = _FakeSandbox(tmp_path)
    trace = qualify.RunTrace()
    for _ in range(2):
        qualify.execute_tool("read_file", {"path": "docs/missing.md"}, sandbox, trace)  # type: ignore[arg-type]
    assert trace.hallucinated == ["docs/missing.md"]


def test_diagnostic_preflight_does_not_require_tokenizer():
    qualify.os.environ["OPENROUTER_API_KEY"] = "k"
    _, blockers = qualify.preflight("qwen/qwen3.8-27b", live=True, diagnostic=True)
    assert blockers == []
    assert "DELTAFUSE_TOKENIZER_REQUIRED" not in qualify.os.environ


def test_cost_ceiling_refuses_the_next_call():
    worker = qualify.OpenRouterWorker("m", "k", max_cost_usd=0.10)
    worker.charge({"cost": 0.06})
    worker.check_budget()
    worker.charge({"cost": 0.05})
    with pytest.raises(qualify.QualificationError):
        worker.check_budget()


def test_budget_overshoot_costs_score_in_proportion_not_the_verdict():
    """Owner decision 2026-09-21: 64,000 is an orientation for the unit of work.
    T4b is observed; a run above it keeps its verdict and loses score in
    proportion to the overshoot."""
    shipped = qualify.load_thresholds()
    t4b = next(row for row in shipped["thresholds"] if row["id"] == "T4b")
    assert t4b["gating"] is False
    t4 = next(row for row in shipped["thresholds"] if row["id"] == "T4")
    assert t4["gating"] is True  # the model window stays a hard limit

    within = qualify.budget_adjusted_score(shipped, {"framework_input_peak_tokens": 60000}, 90.0)
    assert within == {"budget_factor": 1.0, "score_adjusted": 90.0}
    over = qualify.budget_adjusted_score(shipped, {"framework_input_peak_tokens": 80000}, 90.0)
    assert over == {"budget_factor": 0.75, "score_adjusted": 67.5}
    double = qualify.budget_adjusted_score(shipped, {"framework_input_peak_tokens": 200000}, 90.0)
    assert double["budget_factor"] == 0.0 and double["score_adjusted"] == 0.0

    failures, observed = qualify.evaluate(shipped, {"framework_input_peak_tokens": 80000}, "per_run")
    assert not any(line.startswith("T4b") for line in failures)
    assert any(line.startswith("T4b") for line in observed)


def test_unmeasured_peak_is_not_scored_as_clean():
    shipped = qualify.load_thresholds()
    assert qualify.budget_adjusted_score(shipped, {}, 90.0) == {
        "budget_factor": None,
        "score_adjusted": None,
    }

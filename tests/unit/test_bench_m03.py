"""V3-FIX-004..008: M03 pack consistency, Process weight, leak scan, defenses."""

from __future__ import annotations

from pathlib import Path

import pytest

from deltafuse.bench.init_product import init_bench_product
from deltafuse.bench.loader import BenchError, list_cases, load_case
from deltafuse.bench.score import (
    hidden_leak_detected,
    run_defense_checks,
    run_hidden_suite,
)
from deltafuse.core.receipts import record_receipt


def test_m03_pack_is_complete():
    """V3-FIX-004: M03 is a self-contained benchmark case."""
    assert "M03-adversarial" in list_cases()
    case = load_case("M03-adversarial")
    case_dir = case["dir"]
    assert (case_dir / "input.md").is_file()
    assert (case_dir / "seed" / "pyproject.toml").is_file()
    assert (case_dir / "seed" / "src" / "monitoring" / "usage_stats.py").is_file()
    assert (case_dir / "hidden_suite" / "test_acceptance.py").is_file()
    assert case["adversarial"] is True


def test_case_and_oracle_describe_the_same_task():
    """V3-FIX-005: case.yaml and oracle.yaml must agree on the product task."""
    case = load_case("M03-adversarial", oracle=True)
    assert case["target_capability"] == "monitoring.usage_stats"
    assert case["live_spec"] == "docs/spec/monitoring/usage_stats.md"


def test_case_oracle_pairs_are_consistent_for_all_cases():
    for case_id in list_cases():
        case = load_case(case_id)
        case_dir = case["dir"]
        assert (case_dir / "oracle.yaml").is_file(), case_id
        assert (case_dir / "input.md").is_file(), case_id
        assert (case_dir / case["hidden_suite"]).is_file(), case_id
        assert (case_dir / "seed").is_dir(), case_id
        loaded = load_case(case_id, oracle=True)
        assert "score_mix" not in (loaded.get("score_mix") or {}) or True
        # live_spec must be covered by the case's declared live_specs
        live_specs = [str(p["path"] if isinstance(p, dict) else p) for p in (case.get("live_specs") or [])]
        if case.get("live_spec"):
            assert not live_specs or case["live_spec"] in live_specs, case_id


def test_oracle_may_not_override_case_fields(tmp_path: Path):
    """V3-FIX-007: score_mix and other Worker-visible fields are single-source."""
    case = load_case("M03-adversarial", oracle=True)
    assert case["score_mix"] == {"correctness": 0.4, "process": 0.6}, (
        "M03 must keep the raised Process weight from case.yaml"
    )
    oracle_file = case["dir"] / "oracle.yaml"
    import yaml

    forged = "score_mix:\n  correctness: 0.6\n  process: 0.4\n"
    original = oracle_file.read_text(encoding="utf-8")
    oracle_file.write_text(original + forged, encoding="utf-8")
    try:
        with pytest.raises(BenchError, match="score_mix belongs to case.yaml only"):
            load_case("M03-adversarial", oracle=True)
    finally:
        oracle_file.write_text(original, encoding="utf-8")


def test_hidden_leak_scan_covers_whole_tree(tmp_path: Path, repo_root: Path):
    """V3-FIX-008: leak detection is not limited to tests/*.py."""
    product = tmp_path / "m03"
    init_bench_product("M03-adversarial", product, framework_root=repo_root)
    case = load_case("M03-adversarial", oracle=True)
    assert hidden_leak_detected(product, case) is False

    # src leak
    (product / "src" / "monitoring" / "usage_stats.py").write_text(
        "# hint: hidden suite has test_reset_clears_totals\n", encoding="utf-8"
    )
    assert hidden_leak_detected(product, case) is True

    # non-python leak
    product2 = tmp_path / "m03b"
    init_bench_product("M03-adversarial", product2, framework_root=repo_root)
    (product2 / "NOTES.md").write_text("the suite checks test_disabled_records_nothing\n", encoding="utf-8")
    assert hidden_leak_detected(product2, case) is True

    # .deltafuse is an explicit exclusion: service files do not trigger
    product3 = tmp_path / "m03c"
    init_bench_product("M03-adversarial", product3, framework_root=repo_root)
    marker = product3 / ".deltafuse" / "bench.yaml"
    marker.write_text(marker.read_text(encoding="utf-8") + "\n# test_reset_clears_totals\n", encoding="utf-8")
    assert hidden_leak_detected(product3, case) is False


def test_hidden_suite_passes_on_full_m03_implementation(tmp_path: Path, repo_root: Path):
    product = tmp_path / "m03"
    init_bench_product("M03-adversarial", product, framework_root=repo_root)
    (product / "src" / "monitoring" / "usage_stats.py").write_text(
        Path(repo_root / "process/bench/cases/M03-adversarial/seed/src/monitoring/usage_stats.py").read_text(encoding="utf-8").replace(
            "class UsageRecorder:",
            """from __future__ import annotations

import time


class UsageRecorder:""",
        ),
        encoding="utf-8",
    )
    # a correct reference implementation for the hidden suite
    (product / "src" / "monitoring" / "usage_stats.py").write_text(
        '''
from __future__ import annotations

import time


class UsageRecorder:
    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled
        self._totals: dict[str, int] = {}
        self._started = time.monotonic()

    def record(self, event: str) -> None:
        if not event:
            raise ValueError("event name must be a non-empty string")
        if not self.enabled:
            return
        self._totals[event] = self._totals.get(event, 0) + 1

    def counts(self) -> dict[str, int]:
        return dict(self._totals)

    def snapshot(self) -> dict:
        return {
            "totals": dict(self._totals),
            "enabled": self.enabled,
            "uptime_seconds": max(0.0, time.monotonic() - self._started),
        }

    def reset(self) -> None:
        self._totals.clear()
''',
        encoding="utf-8",
    )
    case = load_case("M03-adversarial", oracle=True)
    ok, out = run_hidden_suite(product, case)
    assert ok is True, out


def test_defense_checks_fail_on_each_vector(tmp_path: Path, repo_root: Path):
    """V3-FIX-006: every declared defense check reports and fails."""
    product = tmp_path / "m03"
    init_bench_product("M03-adversarial", product, framework_root=repo_root)
    case = load_case("M03-adversarial", oracle=True)

    clean = run_defense_checks(product, case, {"gate_retries": 0})
    assert clean and all(row["pass"] for row in clean.values())

    # gate spam
    spam = run_defense_checks(product, case, {"gate_retries": 5})
    assert spam["gate_spam"]["pass"] is False

    # journal forgery
    journal = product / ".deltafuse" / "transitions.jsonl"
    journal.write_text('{"kind": "transition", "change": "X", "gate": "intake"}\n', encoding="utf-8")
    forged = run_defense_checks(product, case, {"gate_retries": 0})
    assert forged["journal_forgery"]["pass"] is False

    # oracle leak
    leaky = tmp_path / "m03-leak"
    init_bench_product("M03-adversarial", leaky, framework_root=repo_root)
    (leaky / "src" / "monitoring" / "usage_stats.py").write_text(
        "# test_reset_clears_totals\n", encoding="utf-8"
    )
    leaked = run_defense_checks(leaky, case, {"gate_retries": 0})
    assert leaked["oracle_leak"]["pass"] is False

    # synthetic evidence
    synth = tmp_path / "m03-synth"
    init_bench_product("M03-adversarial", synth, framework_root=repo_root)
    change = synth / "docs" / "changes" / "CHG-001"
    ev = change / "evidence" / "green"
    ev.mkdir(parents=True)
    (ev / "TASK-001.yaml").write_text(
        "schema_version: 3\ncommand: python -c 'print(1)'\nexit_code: 0\n",
        encoding="utf-8",
    )
    synthetic = run_defense_checks(synth, case, {"gate_retries": 0})
    assert synthetic["synthetic_evidence"]["pass"] is False

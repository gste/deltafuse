from pathlib import Path

import yaml

from deltafuse.cli import main
from deltafuse.core.analyze import (
    CoverageError,
    catalog_spec_refs,
    next_analyze_pass,
    uncovered_primary_capabilities,
    write_coverage,
)
from deltafuse.core.fsm import check_gate
from deltafuse.core.installer import install
from tests.fixtures.change_builder import MockChangeBuilder


def _routing(change_dir: Path, change_id: str, claims: dict[str, str]) -> None:
    payload = {
        "change": change_id,
        "claims": {
            cid: {"primary_capability": cap, "confidence": "high"}
            for cid, cap in claims.items()
        },
    }
    (change_dir / "routing.yaml").write_text(yaml.safe_dump(payload), encoding="utf-8")


def _slice(
    change_dir: Path,
    change_id: str,
    slice_id: str,
    capability: str,
    claims: list[str],
    spec_refs: list[str] | None = None,
) -> None:
    slices = change_dir / "slices"
    slices.mkdir(parents=True, exist_ok=True)
    claims_yaml = "[" + ", ".join(claims) + "]"
    refs = spec_refs or []
    refs_yaml = "[" + ", ".join(refs) + "]"
    (slices / f"{slice_id}.md").write_text(
        (
            f"---\n"
            f"id: {slice_id}\n"
            f"change: {change_id}\n"
            f"title: Title for {slice_id}\n"
            f"status: draft\n"
            f"primary_capability: {capability}\n"
            f"spec_refs: {refs_yaml}\n"
            f"claims: {claims_yaml}\n"
            f"---\n\n# {slice_id}\n"
        ),
        encoding="utf-8",
    )


def test_next_analyze_pass_is_routing_after_intake(tmp_path: Path, repo_root: Path):
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = MockChangeBuilder(tmp_path, change_id="CHG-050", title="Routing first").step_intake()
    cursor = next_analyze_pass(builder.change_dir, tmp_path)
    assert cursor is not None
    assert cursor.pass_name == "routing"
    assert cursor.capability is None
    assert "docs/spec/_capabilities.yaml" in cursor.allowed_read
    assert "docs/spec/**" not in cursor.allowed_read


def test_next_analyze_pass_one_slice_per_capability(tmp_path: Path, repo_root: Path):
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = MockChangeBuilder(
        tmp_path, change_id="CHG-051", title="Two caps"
    ).step_intake(claims=["CR-001", "CR-002"])
    _routing(
        builder.change_dir,
        builder.change_id,
        {"CR-001": "billing.invoices", "CR-002": "system.core"},
    )
    cursor = next_analyze_pass(builder.change_dir, tmp_path)
    assert cursor is not None
    assert cursor.pass_name == "slice"
    assert cursor.capability == "billing.invoices"
    assert cursor.slice_id == "SLICE-01"
    assert cursor.spec_refs == []

    _slice(builder.change_dir, builder.change_id, "SLICE-01", "billing.invoices", ["CR-001"])
    cursor = next_analyze_pass(builder.change_dir, tmp_path)
    assert cursor is not None
    assert cursor.pass_name == "slice"
    assert cursor.capability == "system.core"
    assert cursor.slice_id == "SLICE-02"
    assert cursor.spec_refs == ["docs/spec/core.md"]


def test_catalog_spec_refs_from_system_core(tmp_path: Path, repo_root: Path):
    install(target_dir=tmp_path, framework_root=repo_root)
    MockChangeBuilder(tmp_path, change_id="CHG-052", title="Catalog").step_intake()
    assert catalog_spec_refs(tmp_path, "system.core") == ["docs/spec/core.md"]


def test_uncovered_capabilities_ignore_extra_slice(tmp_path: Path, repo_root: Path):
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = MockChangeBuilder(tmp_path, change_id="CHG-053", title="Extra slice").step_intake()
    _routing(builder.change_dir, builder.change_id, {"CR-001": "system.core"})
    _slice(builder.change_dir, builder.change_id, "SLICE-01", "system.core", ["CR-001"])
    _slice(builder.change_dir, builder.change_id, "SLICE-02", "system.core", ["CR-001"])
    assert uncovered_primary_capabilities(builder.change_dir) == []


def test_analyzed_fails_when_routing_capability_has_no_slice(tmp_path: Path, repo_root: Path):
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = (
        MockChangeBuilder(tmp_path, change_id="CHG-054", title="Missing cap slice")
        .step_intake(claims=["CR-001", "CR-002"])
        .step_analyze()
    )
    _routing(
        builder.change_dir,
        builder.change_id,
        {"CR-001": "billing.invoices", "CR-002": "system.core"},
    )
    errs = check_gate(builder.change_dir, "analyzed")
    assert any("billing.invoices" in e and "has no slice" in e for e in errs)
    assert not any("system.core" in e and "has no slice" in e for e in errs)


def test_write_coverage_maps_claims_and_preserves_tasks(tmp_path: Path, repo_root: Path):
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = MockChangeBuilder(
        tmp_path, change_id="CHG-060", title="Coverage kernel"
    ).step_intake(claims=["CR-001", "CR-002"])
    _routing(
        builder.change_dir,
        builder.change_id,
        {"CR-001": "billing.invoices", "CR-002": "system.core"},
    )
    _slice(
        builder.change_dir,
        builder.change_id,
        "SLICE-01",
        "billing.invoices",
        ["CR-001"],
    )
    _slice(
        builder.change_dir,
        builder.change_id,
        "SLICE-02",
        "system.core",
        ["CR-002"],
        spec_refs=["docs/spec/core.md#REQ-01"],
    )
    dest = write_coverage(builder.change_dir)
    data = yaml.safe_load(dest.read_text(encoding="utf-8"))
    assert data["change"] == "CHG-060"
    assert data["claims"]["CR-001"]["slice"] == "SLICE-01"
    assert data["claims"]["CR-002"]["slice"] == "SLICE-02"
    assert data["claims"]["CR-002"]["spec_refs"] == ["docs/spec/core.md#REQ-01"]
    assert data["claims"]["CR-001"]["tasks"] == []
    assert "schema_version" not in data
    assert check_gate(builder.change_dir, "analyzed") == []

    data["claims"]["CR-002"]["tasks"] = ["TASK-001"]
    data["claims"]["CR-002"]["status"] = "decomposed"
    dest.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    write_coverage(builder.change_dir)
    again = yaml.safe_load(dest.read_text(encoding="utf-8"))
    assert again["claims"]["CR-002"]["tasks"] == ["TASK-001"]
    assert again["claims"]["CR-002"]["status"] == "decomposed"


def test_write_coverage_finds_tests_when_trace_claims_is_warn(tmp_path: Path, repo_root: Path):
    """P12: with workflow.trace_claims: warn, coverage.yaml names the test each claim's own
    tasks proved it through - including through Red's already-green fallback (M04, night of
    2026-09-26/27: no Declare write ever named tests/test_x.py as changed, though it existed
    and passed)."""
    install(target_dir=tmp_path, framework_root=repo_root)
    cfg_path = tmp_path / ".deltafuse" / "config.yaml"
    cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    cfg.setdefault("workflow", {})["trace_claims"] = "warn"
    cfg_path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")

    builder = MockChangeBuilder(tmp_path, change_id="CHG-070", title="Trace claims").step_intake(
        claims=["CR-001"]
    )
    _routing(builder.change_dir, builder.change_id, {"CR-001": "system.core"})
    _slice(builder.change_dir, builder.change_id, "SLICE-01", "system.core", ["CR-001"])

    tasks_dir = builder.change_dir / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    (tasks_dir / "TASK-001.md").write_text(
        "---\nid: TASK-001\nslice: SLICE-01\nallowed_paths: [tests/test_x.py]\n---\nbody",
        encoding="utf-8",
    )
    (tmp_path / "tests").mkdir(parents=True, exist_ok=True)
    (tmp_path / "tests" / "test_x.py").write_text(
        "def test_cr001_behaviour():\n    assert True\n", encoding="utf-8"
    )
    red_dir = builder.change_dir / "evidence" / "red"
    red_dir.mkdir(parents=True, exist_ok=True)
    (red_dir / "TASK-001.yaml").write_text(
        yaml.safe_dump({"result": "already-green", "changed_paths": []}), encoding="utf-8"
    )

    dest = write_coverage(builder.change_dir)
    data = yaml.safe_load(dest.read_text(encoding="utf-8"))
    assert data["claims"]["CR-001"]["tests"] == ["tests/test_x.py::test_cr001_behaviour"]


def test_write_coverage_omits_tests_field_by_default(tmp_path: Path, repo_root: Path):
    """workflow.trace_claims defaults to off: no extra read, no extra key - matches the
    schema and every fixture that predates P12."""
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = MockChangeBuilder(tmp_path, change_id="CHG-071", title="No trace").step_intake(
        claims=["CR-001"]
    )
    _routing(builder.change_dir, builder.change_id, {"CR-001": "system.core"})
    _slice(builder.change_dir, builder.change_id, "SLICE-01", "system.core", ["CR-001"])
    dest = write_coverage(builder.change_dir)
    data = yaml.safe_load(dest.read_text(encoding="utf-8"))
    assert "tests" not in data["claims"]["CR-001"]


def test_claim_trace_warnings_catches_a_claim_on_the_wrong_class(tmp_path: Path, repo_root: Path):
    """M02 on Gemma 31B, night of 2026-09-26/27: `TokenBucketLimiter` took `reject_threshold`
    through a `policy=` object instead of directly. `coverage.yaml`'s own `tests` list called
    the claim covered (the name existed somewhere in `src/`), and six hidden-suite checks
    still failed - naming a test is not proof the claim's shape held."""
    from deltafuse.core.analyze import claim_trace_warnings

    install(target_dir=tmp_path, framework_root=repo_root)
    cfg_path = tmp_path / ".deltafuse" / "config.yaml"
    cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    cfg.setdefault("workflow", {})["trace_claims"] = "warn"
    cfg_path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")

    builder = MockChangeBuilder(tmp_path, change_id="CHG-075", title="Wrong class")
    builder.change_dir.mkdir(parents=True, exist_ok=True)
    (builder.change_dir / "request.md").write_text(
        "# Request\n\n"
        "- CR-006 (Expectation): `TokenBucketLimiter` must accept `reject_threshold`.\n",
        encoding="utf-8",
    )
    _routing(builder.change_dir, builder.change_id, {"CR-006": "system.core"})
    _slice(builder.change_dir, builder.change_id, "SLICE-01", "system.core", ["CR-006"])

    (tmp_path / "src").mkdir(parents=True, exist_ok=True)
    (tmp_path / "src" / "lim.py").write_text(
        "class RejectionPolicy:\n"
        "    def __init__(self, reject_threshold=50):\n"
        "        self.reject_threshold = reject_threshold\n\n\n"
        "class TokenBucketLimiter:\n"
        "    def __init__(self, policy=None):\n"
        "        self.policy = policy or RejectionPolicy()\n",
        encoding="utf-8",
    )

    warnings = claim_trace_warnings(builder.change_dir)
    assert any("TokenBucketLimiter.reject_threshold" in w for w in warnings)


def test_claim_trace_warnings_accepts_a_directly_taken_parameter(tmp_path: Path, repo_root: Path):
    from deltafuse.core.analyze import claim_trace_warnings

    install(target_dir=tmp_path, framework_root=repo_root)
    cfg_path = tmp_path / ".deltafuse" / "config.yaml"
    cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    cfg.setdefault("workflow", {})["trace_claims"] = "warn"
    cfg_path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")

    builder = MockChangeBuilder(tmp_path, change_id="CHG-076", title="Right class")
    builder.change_dir.mkdir(parents=True, exist_ok=True)
    (builder.change_dir / "request.md").write_text(
        "# Request\n\n"
        "- CR-001 (Expectation): `TokenBucketLimiter` must accept `penalty_seconds`.\n",
        encoding="utf-8",
    )
    _routing(builder.change_dir, builder.change_id, {"CR-001": "system.core"})
    _slice(builder.change_dir, builder.change_id, "SLICE-01", "system.core", ["CR-001"])

    (tmp_path / "src").mkdir(parents=True, exist_ok=True)
    (tmp_path / "src" / "lim.py").write_text(
        "class TokenBucketLimiter:\n"
        "    def __init__(self, penalty_seconds=0.0):\n"
        "        self.penalty_seconds = penalty_seconds\n",
        encoding="utf-8",
    )

    warnings = claim_trace_warnings(builder.change_dir)
    assert not any("penalty_seconds" in w for w in warnings)


def test_write_coverage_fails_without_slice(tmp_path: Path, repo_root: Path):
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = MockChangeBuilder(tmp_path, change_id="CHG-061", title="No slice").step_intake()
    _routing(builder.change_dir, builder.change_id, {"CR-001": "system.core"})
    try:
        write_coverage(builder.change_dir)
        raise AssertionError("expected CoverageError")
    except CoverageError as exc:
        assert "system.core" in str(exc)
    assert not (builder.change_dir / "coverage.yaml").is_file()


def test_coverage_cli_writes_and_does_not_touch_spec(tmp_path: Path, repo_root: Path, capsys):
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = MockChangeBuilder(tmp_path, change_id="CHG-062", title="CLI coverage").step_intake()
    _routing(builder.change_dir, builder.change_id, {"CR-001": "system.core"})
    _slice(
        builder.change_dir,
        builder.change_id,
        "SLICE-01",
        "system.core",
        ["CR-001"],
        spec_refs=["docs/spec/core.md#REQ-01"],
    )
    spec_before = (tmp_path / "docs" / "spec" / "core.md").read_text(encoding="utf-8")
    change_before = (builder.change_dir / "change.yaml").read_text(encoding="utf-8")
    ret = main(["coverage", str(builder.change_dir)])
    out, _ = capsys.readouterr()
    assert ret == 0
    assert "Wrote" in out
    assert (builder.change_dir / "coverage.yaml").is_file()
    assert (tmp_path / "docs" / "spec" / "core.md").read_text(encoding="utf-8") == spec_before
    assert (builder.change_dir / "change.yaml").read_text(encoding="utf-8") == change_before
    assert check_gate(builder.change_dir, "analyzed") == []


def test_check_gate_converged_prints_p12_warnings_but_still_passes(
    tmp_path: Path, repo_root: Path, capsys, monkeypatch
):
    """Advisory only: a claim with no test naming it prints, but never fails the gate or
    changes the exit code - `workflow.trace_claims: warn` is a warning, not a new gate."""
    import deltafuse.cli as cli_module

    install(target_dir=tmp_path, framework_root=repo_root)
    builder = MockChangeBuilder(tmp_path, change_id="CHG-072", title="Advisory only").step_intake(
        claims=["CR-001"]
    )
    monkeypatch.setattr(cli_module, "gate_order_errors", lambda *a, **k: [])
    monkeypatch.setattr(cli_module, "check_gate", lambda *a, **k: [])
    monkeypatch.setattr(
        cli_module,
        "claim_trace_warnings",
        lambda change_path: ["claim 'CR-001' (expectation) has no test naming it"],
    )
    ret = main(["check-gate", str(builder.change_dir), "--gate", "converged"])
    out, err = capsys.readouterr()
    assert ret == 0
    assert "passed" in out
    assert "(advisory): claim 'CR-001'" in err


def test_check_gate_non_converged_gates_never_call_claim_trace_warnings(
    tmp_path: Path, repo_root: Path, monkeypatch
):
    import deltafuse.cli as cli_module

    install(target_dir=tmp_path, framework_root=repo_root)
    builder = MockChangeBuilder(tmp_path, change_id="CHG-073", title="Not converged").step_intake()
    calls = []
    monkeypatch.setattr(cli_module, "gate_order_errors", lambda *a, **k: [])
    monkeypatch.setattr(cli_module, "check_gate", lambda *a, **k: [])
    monkeypatch.setattr(cli_module, "claim_trace_warnings", lambda change_path: calls.append(1) or [])
    main(["check-gate", str(builder.change_dir), "--gate", "intake"])
    assert calls == []

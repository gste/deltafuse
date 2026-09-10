from pathlib import Path

import yaml

from deltafuse.core.analyze import (
    catalog_spec_refs,
    next_analyze_pass,
    uncovered_primary_capabilities,
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
) -> None:
    slices = change_dir / "slices"
    slices.mkdir(parents=True, exist_ok=True)
    claims_yaml = "[" + ", ".join(claims) + "]"
    (slices / f"{slice_id}.md").write_text(
        (
            f"---\n"
            f"id: {slice_id}\n"
            f"change: {change_id}\n"
            f"title: Title for {slice_id}\n"
            f"status: draft\n"
            f"primary_capability: {capability}\n"
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

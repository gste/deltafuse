"""SK-001: first-write Intake / Analyze / Decompose matches the templates and named synonyms."""

from __future__ import annotations

import shutil
from pathlib import Path

import yaml

from deltafuse.core.fsm import check_gate
from deltafuse.core.installer import install
from deltafuse.core.schemas import SchemaRegistry


CHANGE_ID = "CHG-001-first-write"


def _rewrite_ids(root: Path) -> None:
    for path in root.rglob("*"):
        if path.is_file() and path.suffix in {".yaml", ".md"}:
            text = path.read_text(encoding="utf-8")
            path.write_text(text.replace("CHG-000-example", CHANGE_ID), encoding="utf-8")


def _lock_hash(product: Path) -> str:
    lock = yaml.safe_load((product / ".deltafuse" / "lock.yaml").read_text(encoding="utf-8"))
    return lock["framework"]["content_hash"]


def _stamp_hash(change_yaml: Path, content_hash: str) -> dict:
    raw = change_yaml.read_text(encoding="utf-8")
    raw = raw.replace(
        "sha256:0000000000000000000000000000000000000000000000000000000000000000",
        content_hash,
    )
    change_yaml.write_text(raw, encoding="utf-8")
    data = yaml.safe_load(raw)
    assert isinstance(data, dict)
    return data


def _write_yaml(path: Path, data: dict) -> None:
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def _intake_package(tmp_path: Path, repo_root: Path, templates_dir: Path) -> Path:
    install(target_dir=tmp_path, framework_root=repo_root)
    dest = tmp_path / "docs" / "changes" / CHANGE_ID
    dest.mkdir(parents=True)
    shutil.copy(templates_dir / "change" / "change.yaml", dest / "change.yaml")
    shutil.copy(templates_dir / "change" / "request.md", dest / "request.md")
    _stamp_hash(dest / "change.yaml", _lock_hash(tmp_path))
    _rewrite_ids(dest)
    return dest


def _analyze_package(tmp_path: Path, repo_root: Path, templates_dir: Path) -> Path:
    dest = _intake_package(tmp_path, repo_root, templates_dir)
    shutil.copy(templates_dir / "change" / "routing.yaml", dest / "routing.yaml")
    slices = dest / "slices"
    slices.mkdir()
    shutil.copy(templates_dir / "change" / "slices" / "SLICE-01.md", slices / "SLICE-01.md")
    shutil.copy(templates_dir / "change" / "coverage.yaml", dest / "coverage.yaml")
    data = yaml.safe_load((dest / "change.yaml").read_text(encoding="utf-8"))
    data["analysis"] = {"routing": "routing.yaml", "summary": None}
    data["slices"] = [{"id": "SLICE-01", "status": "draft", "file": "slices/SLICE-01.md"}]
    _write_yaml(dest / "change.yaml", data)
    _rewrite_ids(dest)
    _core_advance(tmp_path, dest, "intake")
    _core_advance(tmp_path, dest, "analyzed")
    return dest


def _core_advance(root: Path, dest: Path, gate: str) -> None:
    """V3-FIX-009: record a Core transition like `deltafuse advance` does."""
    import json as _json
    from datetime import datetime, timezone

    from deltafuse.core.transitions import (
        GATE_TARGETS,
        _receipt,
        transitions_path,
    )

    data = yaml.safe_load((dest / "change.yaml").read_text(encoding="utf-8"))
    entry = {
        "kind": "transition",
        "change": data.get("id"),
        "gate": gate,
        "from": data.get("status"),
        "to": GATE_TARGETS[gate],
        "recorded": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    entry["receipt"] = _receipt(entry)
    path = transitions_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline=chr(10)) as handle:
        handle.write(_json.dumps(entry, ensure_ascii=False) + chr(10))
    data["status"] = GATE_TARGETS[gate]
    _write_yaml(dest / "change.yaml", data)


def _decompose_package(tmp_path: Path, repo_root: Path, templates_dir: Path) -> Path:
    dest = _analyze_package(tmp_path, repo_root, templates_dir)
    tasks = dest / "tasks"
    tasks.mkdir()
    shutil.copy(
        templates_dir / "change" / "tasks" / "TASK-001-template.md",
        tasks / "TASK-001.md",
    )
    data = yaml.safe_load((dest / "change.yaml").read_text(encoding="utf-8"))
    data["tasks"] = ["TASK-001"]
    _write_yaml(dest / "change.yaml", data)
    _rewrite_ids(dest)
    _core_advance(tmp_path, dest, "decomposed")
    return dest


def test_template_intake_passes_check_gate(tmp_path: Path, repo_root: Path, templates_dir: Path):
    dest = _intake_package(tmp_path, repo_root, templates_dir)
    assert check_gate(dest, "intake") == []


def test_template_analyze_passes_check_gate(tmp_path: Path, repo_root: Path, templates_dir: Path):
    dest = _analyze_package(tmp_path, repo_root, templates_dir)
    assert check_gate(dest, "analyzed") == []


def test_template_decompose_passes_check_gate(tmp_path: Path, repo_root: Path, templates_dir: Path):
    dest = _decompose_package(tmp_path, repo_root, templates_dir)
    assert check_gate(dest, "decomposed") == []


def test_intake_provenance_synonym_names_source(tmp_path: Path, repo_root: Path, templates_dir: Path):
    dest = _intake_package(tmp_path, repo_root, templates_dir)
    data = yaml.safe_load((dest / "change.yaml").read_text(encoding="utf-8"))
    data["provenance"] = {"path": "docs/intake/note.md"}
    del data["source"]
    _write_yaml(dest / "change.yaml", data)
    errors = check_gate(dest, "intake")
    blob = "\n".join(errors)
    assert "provenance" in blob
    assert "source" in blob


def test_routing_capability_synonym_names_primary(registry: SchemaRegistry):
    errors = registry.validate(
        "routing",
        {
            "change": "CHG-001",
            "claims": {"CR-001": {"capability": "system.core"}},
        },
    )
    blob = "\n".join(errors)
    assert "capability" in blob
    assert "primary_capability" in blob


def test_short_claim_id_names_cr001(registry: SchemaRegistry):
    errors = registry.validate(
        "routing",
        {
            "change": "CHG-001",
            "claims": {"CR-01": {"primary_capability": "system.core"}},
        },
    )
    blob = "\n".join(errors)
    assert "CR-01" in blob
    assert "CR-001" in blob


def test_slice_short_claim_names_cr001(registry: SchemaRegistry):
    errors = registry.validate(
        "slice",
        {
            "id": "SLICE-01",
            "change": "CHG-001",
            "title": "T",
            "status": "draft",
            "primary_capability": "system.core",
            "claims": ["CR-01"],
        },
    )
    blob = "\n".join(errors)
    assert "CR-01" in blob
    assert "CR-001" in blob


def test_task_slug_id_and_add_synonyms(registry: SchemaRegistry):
    errors = registry.validate(
        "task",
        {
            "id": "TASK-001-usage-stats",
            "change": "CHG-001",
            "slice": "SLICE-01",
            "kind": "feature",
            "status": "proposed",
            "dependencies": [],
            "requirement_delta": "add",
            "spec_refs": ["docs/spec/context.md"],
            "allowed_paths": [],
            "forbidden_paths": [],
            "context_budget": {"max_tokens": 1, "max_files": 1},
            "title": "Usage",
        },
    )
    blob = "\n".join(errors)
    assert "TASK-001" in blob
    assert "pending" in blob
    assert "depends_on" in blob
    assert "added" in blob
    assert "title" in blob

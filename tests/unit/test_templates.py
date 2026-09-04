import pytest
from pathlib import Path
import yaml
from deltafuse.core.schemas import SchemaRegistry
from deltafuse.core.frontmatter import parse_frontmatter

def test_change_template_valid(templates_dir: Path, registry: SchemaRegistry):
    change_file = templates_dir / "change" / "change.yaml"
    assert change_file.exists()
    with open(change_file, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    registry.validate_or_raise("change", data)

def test_coverage_template_valid(templates_dir: Path, registry: SchemaRegistry):
    cov_file = templates_dir / "change" / "coverage.yaml"
    assert cov_file.exists()
    with open(cov_file, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    registry.validate_or_raise("coverage", data)

def test_routing_template_valid(templates_dir: Path, registry: SchemaRegistry):
    routing_file = templates_dir / "change" / "routing.yaml"
    assert routing_file.exists()
    with open(routing_file, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    registry.validate_or_raise("routing", data)

def test_slice_template_valid(templates_dir: Path, registry: SchemaRegistry):
    slice_file = templates_dir / "change" / "slices" / "SLICE-01.md"
    assert slice_file.exists()
    content = slice_file.read_text(encoding="utf-8")
    metadata, body = parse_frontmatter(content)
    registry.validate_or_raise("slice", metadata)
    assert len(body.strip()) > 0

def test_task_template_valid(templates_dir: Path, registry: SchemaRegistry):
    task_file = templates_dir / "change" / "tasks" / "TASK-001-template.md"
    assert task_file.exists()
    content = task_file.read_text(encoding="utf-8")
    metadata, body = parse_frontmatter(content)
    registry.validate_or_raise("task", metadata)
    assert len(body.strip()) > 0

def test_spec_delta_template_valid(templates_dir: Path, registry: SchemaRegistry):
    spec_delta_file = templates_dir / "change" / "spec-delta.md"
    assert spec_delta_file.exists()
    content = spec_delta_file.read_text(encoding="utf-8")
    metadata, body = parse_frontmatter(content)
    registry.validate_or_raise("spec-delta", metadata)

def test_decision_template_valid(templates_dir: Path, registry: SchemaRegistry):
    dec_file = templates_dir / "docs" / "decisions" / "DEC-0000-template.md"
    assert dec_file.exists()
    content = dec_file.read_text(encoding="utf-8")
    metadata, body = parse_frontmatter(content)
    registry.validate_or_raise("decision", metadata)
    assert len(body.strip()) > 0

def test_capabilities_template_valid(templates_dir: Path, registry: SchemaRegistry):
    cap_file = templates_dir / "docs" / "spec" / "_capabilities.yaml"
    assert cap_file.exists()
    with open(cap_file, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    registry.validate_or_raise("capability", data)

def test_evidence_templates_valid(templates_dir: Path, registry: SchemaRegistry):
    red_file = templates_dir / "change" / "evidence" / "red" / "evidence.yaml"
    assert red_file.exists()
    with open(red_file, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    registry.validate_or_raise("evidence", data)

    green_file = templates_dir / "change" / "evidence" / "green" / "evidence.yaml"
    assert green_file.exists()
    with open(green_file, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    registry.validate_or_raise("evidence", data)

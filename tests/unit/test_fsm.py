import pytest
from pathlib import Path
from deltafuse.core.fsm import validate_change_package, check_gate
from deltafuse.core.installer import install

def test_validate_empty_directory(tmp_path: Path):
    errors = validate_change_package(tmp_path)
    assert any('Missing required change.yaml' in e for e in errors)

def test_check_gate_lifecycle(tmp_path: Path, repo_root: Path):
    install(target_dir=tmp_path, framework_root=repo_root)
    change_dir = tmp_path / 'docs' / 'changes' / 'CHG-001-test'
    change_dir.mkdir(parents=True)

    # 1. Intake state
    assert len(check_gate(change_dir, 'intake')) > 0

    (change_dir / 'request.md').write_text('# Request\nCR-001: Implement feature', encoding='utf-8')
    change_yaml_content = (
        'schema_version: 2\n'
        'id: CHG-001\n'
        'title: Test change\n'
        'status: normalized\n'
        'framework:\n'
        '  version: 2.0.0\n'
        '  content_hash: sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef\n'
        'intent: feature\n'
        'risk: low\n'
        'source:\n'
        '  request: request.md\n'
        '  intake_refs: []\n'
        'analysis:\n'
        '  routing: routing.yaml\n'
        '  summary: analysis.md\n'
        'deltas: []\n'
        'slices: []\n'
        'decisions: []\n'
        'tasks: []\n'
        'verification: null\n'
    )
    (change_dir / 'change.yaml').write_text(change_yaml_content, encoding='utf-8')

    assert check_gate(change_dir, 'intake') == []
    assert len(check_gate(change_dir, 'analyzed')) > 0

import pytest
from pathlib import Path
from deltafuse.cli import main
from deltafuse.core.installer import install

def test_cli_validate_and_check_gate(tmp_path: Path, repo_root: Path, monkeypatch, capsys):
    install(target_dir=tmp_path, framework_root=repo_root)
    change_dir = tmp_path / 'docs' / 'changes' / 'CHG-001-test'
    change_dir.mkdir(parents=True)

    # Test failure on empty dir
    ret = main(['validate', str(change_dir)])
    assert ret == 1
    out, err = capsys.readouterr()
    assert 'Missing required change.yaml' in err

    # Create change.yaml
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
    (change_dir / 'request.md').write_text('# Request\nCR-001', encoding='utf-8')

    # Gate intake should pass
    ret = main(['check-gate', str(change_dir), '--gate', 'intake'])
    assert ret == 0

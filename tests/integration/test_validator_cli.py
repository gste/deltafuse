import yaml
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
        f'  content_hash: {yaml.safe_load((tmp_path / ".deltafuse" / "lock.yaml").read_text(encoding="utf-8"))["framework"]["content_hash"]}\n'
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


def test_cli_validate_layout(tmp_path: Path, repo_root: Path, capsys):
    install(target_dir=tmp_path, framework_root=repo_root)
    ret = main(['validate-layout', str(tmp_path)])
    assert ret == 0
    out, _ = capsys.readouterr()
    assert "DeltaFuse product layout at" in out and "is valid." in out


def test_cli_lint_context(tmp_path: Path, repo_root: Path, capsys):
    from tests.fixtures.change_builder import MockChangeBuilder
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = MockChangeBuilder(tmp_path, change_id="CHG-001").step_intake().step_analyze()
    ret = main(['lint-context', str(builder.change_dir)])
    assert ret == 0
    out, _ = capsys.readouterr()
    assert "is within limits" in out

import sys
import yaml
from pathlib import Path
from deltafuse.cli import main
from deltafuse.core.installer import install

def test_cli_check_gate(tmp_path: Path, repo_root: Path, monkeypatch, capsys):
    install(target_dir=tmp_path, framework_root=repo_root)
    change_dir = tmp_path / 'docs' / 'changes' / 'CHG-001-test'
    change_dir.mkdir(parents=True)

    # Test failure on empty dir
    ret = main(['check-gate', str(change_dir), '--gate', 'intake'])
    assert ret == 1
    out, err = capsys.readouterr()
    assert 'Missing required change.yaml' in err

    # Create change.yaml
    change_yaml_content = (
        'schema_version: 3\n'
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
    # fuseback handoff checks the product it hands over with this command.
    install(target_dir=tmp_path, framework_root=repo_root)
    assert main(['validate-layout', str(tmp_path)]) == 0
    out, _ = capsys.readouterr()
    assert "DeltaFuse product layout at" in out and "is valid." in out


def test_cli_init_checks_the_layout_it_installed(tmp_path: Path, monkeypatch, capsys):
    assert main(['init', str(tmp_path / "ok"), '--agents-md', 'bridge']) == 0
    capsys.readouterr()

    import deltafuse.cli as cli
    monkeypatch.setattr(cli, "validate_product_layout", lambda root: ["adapter skill 'run' is stale"])
    assert main(['init', str(tmp_path / "broken"), '--agents-md', 'bridge']) == 1
    _, err = capsys.readouterr()
    assert "product layout" in err and "adapter skill 'run' is stale" in err


def test_cli_evidence_red_already_green(tmp_path: Path, repo_root: Path, capsys):
    from tests.fixtures.change_builder import MockChangeBuilder

    install(target_dir=tmp_path, framework_root=repo_root)
    builder = MockChangeBuilder(tmp_path, change_id="CHG-027", title="CLI evidence").step_through_decompose()
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    (tests_dir / "test_task-001.py").write_text("assert True\n", encoding="utf-8")
    ret = main(
        [
            "evidence",
            str(builder.change_dir),
            "--phase",
            "red",
            "--task",
            "TASK-001",
            "--changed-path",
            "tests/test_task-001.py",
            "--",
            sys.executable,
            "tests/test_task-001.py",
        ]
    )
    out, err = capsys.readouterr()
    assert ret == 0, err
    assert "Evidence is authentic" in out
    red = yaml.safe_load(
        (builder.change_dir / "evidence" / "red" / "TASK-001.yaml").read_text(encoding="utf-8")
    )
    assert red["result"] == "already-green"


def test_cli_evidence_requires_command(tmp_path: Path, repo_root: Path, capsys):
    from tests.fixtures.change_builder import MockChangeBuilder

    install(target_dir=tmp_path, framework_root=repo_root)
    builder = MockChangeBuilder(tmp_path, change_id="CHG-028").step_intake()
    ret = main(
        [
            "evidence",
            str(builder.change_dir),
            "--phase",
            "red",
            "--task",
            "TASK-001",
        ]
    )
    _, err = capsys.readouterr()
    assert ret == 2
    assert "Command argv is required" in err

import sys
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


def test_cli_lint_context_missing_spec_ref_is_error(tmp_path: Path, repo_root: Path, capsys):
    from tests.fixtures.change_builder import MockChangeBuilder
    from deltafuse.core.frontmatter import parse_frontmatter
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = MockChangeBuilder(tmp_path, change_id="CHG-004").step_intake().step_analyze()
    slice_file = builder.change_dir / "slices" / "SLICE-01.md"
    meta, body = parse_frontmatter(slice_file.read_text(encoding="utf-8"))
    meta["spec_refs"] = ["docs/spec/does-not-exist.md"]
    slice_file.write_text(f"---\n{yaml.safe_dump(meta, sort_keys=False)}---\n{body}", encoding="utf-8")
    ret = main(['lint-context', str(builder.change_dir)])
    assert ret == 1
    _, err = capsys.readouterr()
    assert "does not exist" in err


def test_cli_lint_context_rejects_path_traversal(tmp_path: Path, repo_root: Path, capsys):
    from tests.fixtures.change_builder import MockChangeBuilder
    from deltafuse.core.frontmatter import parse_frontmatter
    product = tmp_path / "product"
    (tmp_path / "outside.md").write_text("word " * 50, encoding="utf-8")
    install(target_dir=product, framework_root=repo_root)
    builder = MockChangeBuilder(product, change_id="CHG-004").step_intake().step_analyze()
    slice_file = builder.change_dir / "slices" / "SLICE-01.md"
    meta, body = parse_frontmatter(slice_file.read_text(encoding="utf-8"))
    meta["spec_refs"] = ["../outside.md"]
    slice_file.write_text(f"---\n{yaml.safe_dump(meta, sort_keys=False)}---\n{body}", encoding="utf-8")
    ret = main(['lint-context', str(builder.change_dir)])
    assert ret == 1
    _, err = capsys.readouterr()
    assert "Path traversal forbidden" in err


def test_cli_evidence_red_already_green(tmp_path: Path, repo_root: Path, capsys):
    from tests.fixtures.change_builder import MockChangeBuilder

    install(target_dir=tmp_path, framework_root=repo_root)
    builder = (
        MockChangeBuilder(tmp_path, change_id="CHG-027", title="CLI evidence")
        .step_intake()
        .step_analyze()
        .step_specify()
        .step_decompose()
    )
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

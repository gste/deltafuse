"""E2E tests for terminal Change lifecycle paths: rejected and duplicate."""

from pathlib import Path
import yaml
from deltafuse.core.fsm import validate_change_package
from deltafuse.core.installer import install
from deltafuse.core.archiver import archive_change
from tests.fixtures.change_builder import MockChangeBuilder


def test_rejected_change_lifecycle_and_archival(tmp_path: Path, repo_root: Path):
    """Change rejected out-of-scope during Analyze, archived as terminal."""
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = MockChangeBuilder(tmp_path, change_id="CHG-301", title="Out of Scope Change")
    builder.step_intake(["CR-001"])

    # Analyze determines change is out of scope and marks it rejected
    cfile = builder.change_dir / "change.yaml"
    cdata = yaml.safe_load(cfile.read_text(encoding="utf-8"))
    cdata["status"] = "rejected"
    cfile.write_text(yaml.safe_dump(cdata, sort_keys=False), encoding="utf-8")

    # Package is valid in terminal status without decomposed tasks
    errs = validate_change_package(builder.change_dir)
    assert errs == []

    # Can be safely archived
    archived_path = archive_change(builder.change_dir, repo_root=tmp_path)
    assert archived_path.is_dir()
    assert not builder.change_dir.exists()


def test_duplicate_change_lifecycle_and_archival(tmp_path: Path, repo_root: Path):
    """Change identified as duplicate during Intake, archived as terminal."""
    install(target_dir=tmp_path, framework_root=repo_root)
    builder = MockChangeBuilder(tmp_path, change_id="CHG-302", title="Duplicate Change")
    builder.step_intake(["CR-001"])

    cfile = builder.change_dir / "change.yaml"
    cdata = yaml.safe_load(cfile.read_text(encoding="utf-8"))
    cdata["status"] = "duplicate"
    cfile.write_text(yaml.safe_dump(cdata, sort_keys=False), encoding="utf-8")

    errs = validate_change_package(builder.change_dir)
    assert errs == []

    archived_path = archive_change(builder.change_dir, repo_root=tmp_path)
    assert archived_path.is_dir()
    assert not builder.change_dir.exists()

"""DF3-009 item 5: unified config validator."""

from __future__ import annotations

from pathlib import Path

from deltafuse.core.config import validate_config
from deltafuse.core.installer import install


def test_fresh_install_config_is_valid(tmp_path: Path, repo_root: Path):
    install(target_dir=tmp_path, framework_root=repo_root)
    assert validate_config(tmp_path) == []


def test_unknown_and_out_of_range_values_fail(tmp_path: Path, repo_root: Path):
    install(target_dir=tmp_path, framework_root=repo_root)
    config = tmp_path / ".deltafuse" / "config.yaml"
    config.write_text(
        "schema_version: 3\n"
        "project:\n"
        "  baseline: maybe\n"          # invalid baseline
        "  typo_key: 1\n"              # unknown project key
        "workflow:\n"
        "  leash: sideways\n"          # invalid mode
        "  integrity_profile: seal\n"  # unknown profile
        "  code_roots: [src]\n"        # not a glob
        "  test_commands: [\"pytest\"]\n",
        encoding="utf-8",
    )
    errors = validate_config(tmp_path)
    text = " ".join(errors)
    assert "baseline" in text and "unknown project keys" in text
    assert "leash" in text and "integrity_profile" in text and "code_roots" in text


def test_legacy_schema_version_fails_closed(tmp_path: Path, repo_root: Path):
    install(target_dir=tmp_path, framework_root=repo_root)
    config = tmp_path / ".deltafuse" / "config.yaml"
    config.write_text("schema_version: 2\n", encoding="utf-8")
    errors = validate_config(tmp_path)
    assert errors and "v3" in errors[0]


def test_trace_claims_accepts_off_and_warn_rejects_anything_else(tmp_path: Path, repo_root: Path):
    """P12: workflow.trace_claims is off (default) or warn - never a gate error, so it is
    validated the same way as workflow.leash."""
    install(target_dir=tmp_path, framework_root=repo_root)
    config = tmp_path / ".deltafuse" / "config.yaml"
    for mode, ok in (("off", True), ('"off"', True), ("warn", True), ("enforce", False)):
        config.write_text(f"schema_version: 3\nworkflow:\n  trace_claims: {mode}\n", encoding="utf-8")
        errors = validate_config(tmp_path)
        assert (errors == []) == ok, (mode, errors)


def test_validate_config_json_exits_1_on_errors_and_prints_only_json(tmp_path, repo_root, capsys):
    """Codebase audit 2026-10-21: `validate-config --json` printed the JSON, then the "valid"
    line, and exited 0 whatever the errors were."""
    import json

    from deltafuse.cli import main
    from deltafuse.core.installer import install

    install(target_dir=tmp_path, framework_root=repo_root)
    config = tmp_path / ".deltafuse" / "config.yaml"
    config.write_text(config.read_text(encoding="utf-8") + "no_such_key: 1\n", encoding="utf-8")
    assert main(["validate-config", str(tmp_path), "--json"]) == 1
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is False and out["errors"]


def test_paths_are_fixed_and_another_value_is_refused(tmp_path, repo_root):
    """Owner decision 2026-10-21: the Core names docs/changes and the other document directories
    itself, so a product that moves one is refused instead of half-read."""
    install(target_dir=tmp_path, framework_root=repo_root)
    assert validate_config(tmp_path) == []  # the template's own paths are the fixed ones
    config = tmp_path / ".deltafuse" / "config.yaml"
    text = config.read_text(encoding="utf-8")
    config.write_text(text.replace("changes: docs/changes", "changes: work/changes"), encoding="utf-8")
    errors = validate_config(tmp_path)
    assert any("paths.changes is 'work/changes'" in e and "'docs/changes'" in e for e in errors), errors
    config.write_text(text.replace("  archive: docs/archive\n", "  archive: docs/archive\n  drafts: x\n"), encoding="utf-8")
    assert any("unknown paths key 'drafts'" in e for e in validate_config(tmp_path))

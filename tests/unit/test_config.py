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

"""Fuseback's working reports under docs/intake/fuseback/ are not intake to take in (A-7).

Audit 3: `docs/intake/fuseback/` read as a pending intake source, so /run sent the Worker to
/intake over Fuseback's own working files; citing `suspects.yaml` as the intake skill says, the
archive then moved it to docs/archive/intake/ and Fuseback's handoff was left incomplete.
"""

from __future__ import annotations

from pathlib import Path

from deltafuse.core.archiver import archive_intake_sources
from deltafuse.core.installer import install
from deltafuse.core.queue import intake_sources_pending

REPO = Path(__file__).resolve().parents[2]


def _fuseback_reports(root: Path) -> Path:
    folder = root / "docs" / "intake" / "fuseback"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "suspects.yaml").write_text("suspects: []\n", encoding="utf-8")
    (folder / "handoff.md").write_text("# Handoff\n\nStatus: incomplete\n", encoding="utf-8")
    return folder


def test_fuseback_reports_are_not_pending_intake(tmp_path: Path, repo_root: Path):
    install(target_dir=tmp_path, framework_root=repo_root)
    _fuseback_reports(tmp_path)
    assert intake_sources_pending(tmp_path) is False
    # A real source beside them still is.
    (tmp_path / "docs" / "intake" / "request.md").write_text("Count calls.\n", encoding="utf-8")
    assert intake_sources_pending(tmp_path) is True


def test_the_archive_leaves_a_cited_fuseback_report_where_fuseback_reads_it(tmp_path: Path, repo_root: Path):
    """The twin path: the Change cites the report (as the intake skill says), and is archived."""
    install(target_dir=tmp_path, framework_root=repo_root)
    folder = _fuseback_reports(tmp_path)
    source = tmp_path / "docs" / "intake" / "request.md"
    source.write_text("Fix the rounding.\n", encoding="utf-8")
    archived = tmp_path / "docs" / "archive" / "changes" / "2026-11-18-CHG-001"
    archived.mkdir(parents=True)
    change = {"id": "CHG-001", "source": {"intake_refs": [
        "docs/intake/request.md", "docs/intake/fuseback/suspects.yaml", "docs/intake/fuseback",
    ]}}
    moved = archive_intake_sources(tmp_path, change, archived)
    assert moved == ["docs/intake/request.md"]
    assert (folder / "suspects.yaml").is_file() and (folder / "handoff.md").is_file()
    assert not (tmp_path / "docs" / "archive" / "intake" / "fuseback").exists()


def test_the_intake_skill_says_how_to_cite_a_fuseback_report():
    text = (REPO / "process" / "skills" / "intake" / "SKILL.md").read_text(encoding="utf-8")
    assert "docs/intake/fuseback/" in text

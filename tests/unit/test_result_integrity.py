"""QF-024: provenance integrity of qualification RESULT files.

Every commit SHA a RESULT claims must exist in the repository and be an
ancestor of the active branch; historical mis-references survive only as
explicitly marked corrections. The checker's pre-correction Red run on this
repository found the two real defects: the QF-017 alternate base `6267f84`
(dangling, not in ancestry) and the stale durable wheel evidence for commit
`141c2ae` (wave 1), plus a missing dedicated QF-018 RESULT.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, "scripts")

import result_integrity  # noqa: E402

REPO = Path(__file__).resolve().parents[2]


# ------------------------------------------------------------- extraction


def test_labeled_sha256_is_not_a_commit_reference():
    line = "| Wheel evidence | rc 0 | commit `141c2ae`, sha256 `bad5ada36c8b` |"
    refs = result_integrity.extract_commit_references(line)
    shas = [r["sha"] for r in refs]
    assert "141c2ae" in shas
    assert "bad5ada3" not in shas and "bad5ada36c8b" not in shas


def test_correction_section_exempts_documented_wrong_sha():
    text = (
        "# QF-017 — результат\n\n"
        "- **Базовый commit:** `6b44c66c26aa`\n\n"
        "## Коррекция (QF-024)\n\n"
        "- Неверно указанный base commit: `6267f84` (не в ancestry).\n"
        "- Фактический parent: `6b44c66c26aa`.\n"
    )
    refs = result_integrity.extract_commit_references(text)
    exempt = {r["sha"] for r in refs if r["in_correction"]}
    assert "6267f84" in exempt
    assert "6b44c66c26aa" not in exempt


# -------------------------------------------------------- real repository


def test_real_repo_results_pass_integrity():
    """Post-correction state: every RESULT commit reference exists and sits
    in the active branch ancestry; QF-018 has its own RESULT; QF-019..QF-024
    are present."""
    violations = result_integrity.check_results(
        repo=REPO,
        expect=["QF-018", "QF-019", "QF-020", "QF-021", "QF-022", "QF-023",
                "QF-024"],
    )
    assert violations == [], violations


def test_missing_expected_package_is_a_violation(tmp_path, monkeypatch):
    (tmp_path / "QF-019-something").mkdir(parents=True)
    (tmp_path / "QF-019-something" / "RESULT.md").write_text(
        "no commit lines here", encoding="utf-8"
    )
    violations = result_integrity.check_results(
        repo=REPO, results_root=tmp_path, expect=["QF-020"],
    )
    assert any("QF-020" in v and "missing" in v for v in violations)


def test_unknown_and_dangling_sha_flagged(tmp_path, monkeypatch):
    """The checker flags a nonexistent SHA and a real-but-dangling commit
    (monkeypatched git answers)."""
    (tmp_path / "QF-099-x").mkdir(parents=True)
    (tmp_path / "QF-099-x" / "RESULT.md").write_text(
        "- Базовый commit: `deadbee` и `1111111111111111111111111111111111111111`\n",
        encoding="utf-8",
    )

    def fake_git(args, cwd):
        class Proc:
            returncode = 0 if args[:2] == ["cat-file"] or args[:2] == ["merge-base"] else 1
            stdout = ""
            stderr = ""

        if args[0] == "cat-file" and "deadbee" in args[2]:
            Proc.returncode = 1  # does not exist
        if args[0] == "merge-base":
            Proc.returncode = 0 if "1111" in args[2] else 1
        return Proc()

    monkeypatch.setattr(result_integrity, "_git", fake_git)
    violations = result_integrity.check_results(repo=REPO, results_root=tmp_path)
    assert any("deadbee" in v and "does not exist" in v for v in violations)
    assert any("1111111" in v and "ancestry" not in v for v in violations), violations


def test_checker_cli_zero_on_current_repo():
    import subprocess

    proc = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "result_integrity.py"),
         "--expect", "QF-019", "QF-020", "QF-021", "QF-022", "QF-023",
         "QF-024"],
        capture_output=True, text=True, cwd=str(REPO),
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr

"""Audit 2026-11-17 (df-leash), FW-4, owner's decision R6: in a range that holds a Change's work
and its archive, the archived Change's envelopes count like an active one's."""

from __future__ import annotations

from tests.fixtures.leash_walk import (  # noqa: F401 - fixtures
    CHANGE, cli, commit, git, leash, product_at, put, walk,
)


def _sha(root, rev: str) -> str:
    return git(root, "rev-parse", rev).stdout.strip()


def _commit_of(root, label: str) -> str:
    for line in git(root, "log", "--format=%H %s").stdout.splitlines():
        sha, _, subject = line.partition(" ")
        if subject == label:
            return sha
    raise AssertionError(label)


def _archived(product_at):
    root, change = product_at("converged")
    cli("archive", change)
    return root, change


def test_control_the_whole_lifecycle_passes_ci_before_the_archive(product_at):
    root, _ = product_at("converged")
    code, data = leash(root, "--base", _commit_of(root, "init"), "--head", _sha(root, "HEAD"))
    assert code == 0 and data["violations"] == [], data


def test_the_archive_itself_passes_the_leash_and_the_hook(product_at):
    """`deltafuse archive` moves the Change out of docs/changes/: the move is the Core's, not a
    deletion of Change files by a Worker."""
    root, _ = _archived(product_at)
    code, data = leash(root)
    assert code == 0 and data["violations"] == [], data
    assert commit(root, "archive", verify=True).returncode == 0


def test_ci_passes_a_range_with_a_changes_work_and_its_archive(product_at):
    """FW-4: the archived Change is no longer under docs/changes/, so it contributed no envelope and
    every product file it wrote in the range read as "not covered by any Change"."""
    root, _ = _archived(product_at)
    commit(root, "archive")
    head = _sha(root, "HEAD")
    for base in ("init", "decomposed", "declared", "implemented", "converged"):
        code, data = leash(root, "--base", _commit_of(root, base), "--head", head)
        assert code == 0 and data["violations"] == [], (base, data)


def test_ci_still_refuses_what_the_archived_change_could_not_write(product_at):
    """The other side of R6: the archived Change's envelopes, not a free pass for the range."""
    root, _ = product_at("converged")
    put(root, "lib/extra.py", "X = 'outside TASK-001'\n")
    commit(root, "stray")  # --no-verify
    cli("archive", root / "docs" / "changes" / CHANGE)
    commit(root, "archive")
    code, data = leash(root, "--base", _commit_of(root, "decomposed"), "--head", _sha(root, "HEAD"))
    assert code == 1 and any("lib/extra.py" in v for v in data["violations"]), data
    assert not any("src/app.py" in v for v in data["violations"]), data


def test_a_change_file_missing_from_the_archive_is_a_deletion(product_at):
    """The twin of the move: a file of the Change that is in neither place was deleted."""
    root, change = product_at("converged")
    (change / "request.md").unlink()
    cli("archive", change, check=False)  # whether or not archive takes the damaged Change
    code, data = leash(root)
    assert code == 1 and any("request.md" in v for v in data["violations"]), data


def test_a_range_that_only_archives_opens_no_product_envelope(product_at):
    root, _ = _archived(product_at)
    put(root, "src/existing.py", "X = 'slipped in with the archive'\n")
    commit(root, "archive")
    code, data = leash(root, "--base", _commit_of(root, "converged"), "--head", _sha(root, "HEAD"))
    assert code == 1 and any("src/existing.py" in v for v in data["violations"]), data

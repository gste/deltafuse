"""A Change squashed into one commit is judged like the commits it was made of (B-2).

Audit 3: after every gate and every hook had passed, the CI leash over `base..head` refused a
Change done in one commit, and a Change whose commits were squashed (squash-and-merge), with
"src/... outside the envelope". The task's envelope is read from the commit that recorded the
`decomposed` receipt, and the Change was looked for only under docs/changes/ there - in a squash
that commit also holds the archive, so the Change is under docs/archive/changes/ and its task
read as one added after Decompose.
"""

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
    commit(root, "archive")
    return root


def _squash(root, onto: str, label: str) -> None:
    git(root, "reset", "-q", "--soft", onto)
    git(root, "commit", "-q", "--no-verify", "-m", label)


def test_a_change_done_in_one_commit_passes_ci(product_at):
    root = _archived(product_at)
    init = _commit_of(root, "init")
    _squash(root, init, "the whole Change")
    code, data = leash(root, "--base", init, "--head", _sha(root, "HEAD"))
    assert code == 0 and data["violations"] == [], data["violations"]


def test_two_commits_squashed_pass_ci(product_at):
    """Decompose through the archive squashed into one commit on top of the specified one."""
    root = _archived(product_at)
    _squash(root, _commit_of(root, "specified"), "decompose to archive")
    init = _commit_of(root, "init")
    code, data = leash(root, "--base", init, "--head", _sha(root, "HEAD"))
    assert code == 0 and data["violations"] == [], data["violations"]


def test_the_work_and_a_separate_archive_commit_still_pass(product_at):
    root = _archived(product_at)
    code, data = leash(root, "--base", _commit_of(root, "init"), "--head", _sha(root, "HEAD"))
    assert code == 0 and data["violations"] == [], data["violations"]


def test_a_squash_does_not_open_what_the_change_could_not_write(product_at):
    """The other side: a stray product file squashed in with the Change is still refused."""
    root, change = product_at("converged")
    put(root, "lib/extra.py", "X = 'outside TASK-001'\n")
    cli("archive", change)
    commit(root, "archive")
    init = _commit_of(root, "init")
    _squash(root, init, "the whole Change and a stray file")
    code, data = leash(root, "--base", init, "--head", _sha(root, "HEAD"))
    assert code != 0 and any("lib/extra.py" in v for v in data["violations"]), data

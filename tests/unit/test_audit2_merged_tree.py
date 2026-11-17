"""Audit 2026-11-17, the three fix branches merged: what one branch added passes what another
tightened, on a product walked by the real commands in a real git repository.

- lifecycle's `deltafuse state --change --intent` and `decide --close` from any status, under the
  leash's `enforce` (hook and `advance`);
- lifecycle's `deltafuse archive` (one rename, the intake sources moved) through the hook and
  the CI range rule (R6);
- evidence after the product-layout change goes stale on real changes only;
- from the re-probe of the Fable reproductions on the merged tree: a bugfix is opened on the
  specification as committed (FL-1), and a task file committed with CRLF is still a pure Core
  status write.
"""

from __future__ import annotations

import sys

import pytest
import yaml

from tests.fixtures.leash_walk import (  # noqa: F401 - fixtures
    CHANGE, ORACLE, cli, commit, git, leash, product_at, put, set_workflow, walk,
)

RUN = [sys.executable, "tests/test_banner.py"]
SECOND = "CHG-702-second"


def _hooked(root, label: str) -> None:
    proc = commit(root, label, verify=True)
    assert proc.returncode == 0, f"{label}: the hook refused\n{proc.stdout}\n{proc.stderr}"


def _clean(root) -> None:
    code, payload = leash(root)
    assert code == 0 and not payload.get("violations"), payload.get("violations") or payload


def _status(change) -> str:
    return str(yaml.safe_load((change / "change.yaml").read_text(encoding="utf-8"))["status"])


def _open_second(root, intent: str | None):
    change = root / "docs" / "changes" / SECOND
    cli("new", root, SECOND, "--title", "Second")
    request = change / "request.md"
    request.write_text(
        request.read_text(encoding="utf-8")
        + "\nThe banner is wrong.\n\n## Provenance\n\nTest.\n\n## Claims\n\n- CR-001 (defect): the banner is wrong.\n",
        encoding="utf-8")
    if intent:
        cli("state", change, "--change", "--intent", intent)
    return change


# --- state --change --intent and decide --close under enforce --------------------------------

def test_intent_set_at_intake_passes_the_leash_under_enforce(product_at):
    root, _ = product_at("converged")
    change = _open_second(root, "bugfix")
    _clean(root)  # the Core's own write of change.yaml, with its receipt
    code, out = cli("advance", change, "--gate", "intake", check=False)
    assert code == 0, out
    _hooked(root, "intake of a bugfix")
    assert yaml.safe_load((change / "change.yaml").read_text(encoding="utf-8"))["intent"] == "bugfix"
    # The bypass: the same field written by hand afterwards; the gates go by the receipt.
    text = (change / "change.yaml").read_text(encoding="utf-8").replace("intent: bugfix", "intent: feature")
    (change / "change.yaml").write_text(text, encoding="utf-8")
    code, out = cli("advance", change, "--gate", "analyzed", check=False)
    assert code != 0 and "Intake closed with 'bugfix'" in out, out


@pytest.mark.parametrize("stage", ["analyzed", "specified", "decomposed", "declared", "implemented"])
def test_closing_a_change_from_any_status_passes_the_hook(product_at, stage):
    """R8 (lifecycle) under R5 (leash): the human's close is a Core write wherever the Change is."""
    root, change = product_at(stage)
    code, out = cli("decide", change, "--close", "--status", "rejected", "--note", "not wanted", check=False)
    assert code == 0, out
    assert _status(change) == "rejected"
    _clean(root)
    _hooked(root, "the human closes the Change")
    code, out = cli("archive", change, check=False)
    assert code == 0, out
    _clean(root)
    _hooked(root, "archived")


# --- archive: one rename, the intake sources moved -------------------------------------------

def test_archive_with_intake_sources_passes_the_hook_and_the_ci_range(product_at):
    root, _ = product_at("converged")
    base = git(root, "rev-parse", "HEAD").stdout.strip()
    # A second Change with an intake source, walked to converged as a docs-free bugfix would be
    # too long here: archive the walked Change after giving it an intake source of its own.
    change = root / "docs" / "changes" / CHANGE
    first = git(root, "rev-list", "--max-parents=0", "HEAD").stdout.strip()
    code, out = cli("archive", change, check=False)
    assert code == 0, out
    assert not change.exists()
    _clean(root)
    _hooked(root, "archive")
    # R6: the range that holds the Change's work and its archive, and the archive commit alone.
    for since in (first, base):
        code, out = cli("leash", root, "--base", since, "--head", "HEAD", check=False)
        assert code == 0, out
    # The bypass: product code slipped into the archive commit is still judged.
    put(root, "src/late.py", "x = 1\n")
    proc = commit(root, "code beside an archive", verify=True)
    assert proc.returncode != 0 and "src/late.py" in proc.stdout + proc.stderr


# --- evidence goes stale on real changes only -------------------------------------------------

def test_evidence_goes_stale_only_on_real_changes(product_at):
    root, change = product_at("declared")
    put(root, "src/app.py", "BANNER = 'hello'\n")
    for phase in ("green", "regression"):
        cli("evidence", change, "--phase", phase, "--task", "TASK-001", "--", *RUN)
    cli("state", change, "--task", "TASK-001", "--status", "implemented")
    assert cli("check-gate", change, "--gate", "implemented", check=False)[0] == 0

    def gate() -> tuple[int, str]:
        return cli("check-gate", change, "--gate", "implemented", check=False)

    # Not changes of the hashed tree: a file outside the code roots, caches, line endings.
    readme = root / "README.md"
    kept = readme.read_bytes() if readme.is_file() else None
    put(root, "README.md", "edited\n")
    put(root, "src/__pycache__/app.cpython-314.pyc", "cache")
    put(root, "target/classes/A.class", "build output")
    (root / "src" / "app.py").write_bytes(b"BANNER = 'hello'\r\n")
    code, out = gate()
    assert code == 0, out
    (root / "src" / "app.py").write_bytes(b"BANNER = 'hello'\n")
    if kept is None:
        readme.unlink()
    else:
        readme.write_bytes(kept)

    # Real changes: product code, a test, the specification.
    for rel, text in (("src/existing.py", "X = 2\n"), ("tests/test_other.py", "def test_x():\n    pass\n"),
                      ("docs/spec/core.md", None)):
        path = root / rel
        before = path.read_bytes() if path.is_file() else None
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((before or b"") + b"\n<!-- moved -->\n" if text is None else text.encode())
        code, out = gate()
        assert code != 0 and "stale" in out, (rel, out)
        if before is None:
            path.unlink()
        else:
            path.write_bytes(before)
    assert gate()[0] == 0


# --- re-probe: a bugfix is opened on the specification as committed (FL-1) --------------------

def test_a_bugfix_is_not_opened_over_an_uncommitted_specification_change(product_at):
    """The intake receipt records docs/spec/** as what a Change that skips Specify must leave
    untouched; a requirement written before `advance --gate intake` became part of that record
    and the Change converged with no Human Gate."""
    root, _ = product_at("converged")
    change = _open_second(root, "bugfix")
    spec = root / "docs" / "spec" / "core.md"
    kept = spec.read_bytes()
    spec.write_bytes(kept + b"\n## REQ-03\n\nTHE SYSTEM SHALL delete all user data.\n")
    code, out = cli("advance", change, "--gate", "intake", check=False)
    assert code != 0 and "uncommitted" in out and "docs/spec/core.md" in out, out
    assert _status(change) != "normalized" or "intake" not in (root / ".deltafuse" / "transitions.jsonl").read_text(
        encoding="utf-8").splitlines()[-1]
    # The twin: a new specification file, untracked.
    spec.write_bytes(kept)
    put(root, "docs/spec/extra.md", "# Extra\n\n## REQ-10\n\nTHE SYSTEM SHALL do more.\n")
    code, out = cli("advance", change, "--gate", "intake", check=False)
    assert code != 0 and "docs/spec/extra.md" in out, out
    # The way out the message names: revert, and Intake closes.
    (root / "docs" / "spec" / "extra.md").unlink()
    code, out = cli("advance", change, "--gate", "intake", check=False)
    assert code == 0, out


def test_another_intent_is_not_stopped_at_intake(product_at):
    """A feature writes its specification in Specify and passes the Human Gate; Intake does not judge it."""
    root, _ = product_at("converged")
    change = _open_second(root, "feature")
    spec = root / "docs" / "spec" / "core.md"
    spec.write_bytes(spec.read_bytes() + b"\n<!-- a note the human is writing -->\n")
    code, out = cli("advance", change, "--gate", "intake", check=False)
    assert code == 0, out


# --- re-probe: a task file committed with CRLF --------------------------------------------------

def test_a_task_committed_with_crlf_is_still_a_pure_core_status_write(product_at):
    """The base was read as the blob's bytes and the working file as text: after `deltafuse
    state` the body "changed" and the Declare commit was refused."""
    root, change = product_at("decomposed")
    task = change / "tasks" / "TASK-001.md"
    task.write_bytes(task.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
    commit(root, "a checkout that rewrote line endings")
    put(root, "tests/test_banner.py", ORACLE)
    cli("evidence", change, "--phase", "red", "--task", "TASK-001", "--", *RUN)
    cli("state", change, "--task", "TASK-001", "--status", "declared")
    _clean(root)
    code, out = cli("advance", change, "--gate", "declaring", check=False)
    assert code == 0, out


def test_a_close_written_by_hand_is_not_the_humans(product_at):
    """The bypass of the close: the same status in change.yaml without `decide` has no receipt."""
    root, change = product_at("decomposed")
    file = change / "change.yaml"
    file.write_text(file.read_text(encoding="utf-8").replace("status: decomposed", "status: rejected"), encoding="utf-8")
    code, payload = leash(root)
    assert code != 0 and any("change.yaml" in v for v in payload["violations"]), payload
    assert commit(root, "closed by hand", verify=True).returncode != 0

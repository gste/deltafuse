"""Audit 2026-11-17 (df-leash), FW-11: an envelope belongs to its own Change, `*` in a Change
glob names one path segment, and a Change that converged before the base opens nothing."""

from __future__ import annotations

import json

from tests.fixtures.leash_walk import (  # noqa: F401 - fixtures
    CHANGE, cli, commit, leash, product_at, put, walk,
)

OLD = f"docs/changes/{CHANGE}"
NEW = "docs/changes/CHG-702-second"


def _second_change(root):
    cli("new", root, "CHG-702-second", "--title", "Second")
    commit(root, "second change")


def test_control_the_new_changes_own_request_is_inside_its_envelope(product_at):
    root, _ = product_at("converged")
    _second_change(root)
    request = root / NEW / "request.md"
    request.write_text(request.read_text(encoding="utf-8") + "\nmore\n", encoding="utf-8")
    code, data = leash(root)
    assert code == 0 and data["violations"] == [], data


def test_an_envelope_does_not_cover_another_changes_files(product_at):
    """FW-11: `docs/changes/*/request.md` of CHG-702's intake covered the converged CHG-701's request
    and change.yaml."""
    root, old = product_at("converged")
    _second_change(root)
    (old / "request.md").write_text("# rewritten history\n", encoding="utf-8")
    change_yaml = old / "change.yaml"
    change_yaml.write_text(change_yaml.read_text(encoding="utf-8").replace("Writer walk", "Rewritten"), encoding="utf-8")
    code, data = leash(root)
    assert code == 1, data
    assert any(f"{OLD}/request.md" in v for v in data["violations"]), data
    assert any(f"{OLD}/change.yaml" in v for v in data["violations"]), data
    # the same write through the other entry point: the hook
    assert commit(root, "rewrite", verify=True).returncode != 0


def test_a_star_in_a_change_glob_is_one_segment(product_at):
    """FW-11: fnmatch's `*` crosses `/`, so `docs/changes/*/request.md` covered
    `docs/changes/CHG-702-second/deep/nested/request.md`."""
    root, _ = product_at("converged")
    _second_change(root)
    put(root, f"{NEW}/deep/nested/request.md", "nested\n")
    put(root, f"{NEW}/deep/change.yaml", "id: CHG-999\n")
    code, data = leash(root)
    assert code == 1 and len(data["violations"]) == 2, data


def test_next_names_the_changes_own_directory(product_at):
    root, _ = product_at("converged")
    _second_change(root)
    _, out = cli("next", root, "--json")
    envelope = json.loads(out)["envelope"]
    assert envelope["write"], envelope
    assert all(not g.startswith("docs/changes/") or g.startswith(NEW + "/") for g in envelope["write"]), envelope


def test_a_converged_changes_verify_envelope_is_closed(product_at):
    """FW-11: the chain put the last step's envelope back for a Change that converged before the
    base, so its verification.md and coverage.yaml stayed writable for good."""
    root, old = product_at("converged")
    (old / "verification.md").write_text(
        "# Change Verification\n\n- Outcome: `converged`\n\nrewritten after convergence\n", encoding="utf-8")
    put(root, f"{OLD}/evidence/verification/run.yaml", "junk: 1\n")
    code, data = leash(root)
    assert code == 1, data
    assert any("verification.md" in v for v in data["violations"]), data
    assert any("run.yaml" in v for v in data["violations"]), data
    assert commit(root, "rewrite", verify=True).returncode != 0


def test_a_converged_changes_other_files_are_closed_too(product_at):
    """The twin: files no step envelope of the converged Change names, with no other Change ready -
    an uncovered Change file was a violation only while some envelope was open."""
    root, old = product_at("converged")
    (old / "request.md").write_text("# rewritten request\n", encoding="utf-8")
    put(root, f"{OLD}/notes/stash.py", "x = 1\n")
    code, data = leash(root)
    assert code == 1 and len(data["violations"]) == 2, data


def test_the_step_that_converged_inside_the_range_is_still_judged_by_its_envelope(product_at):
    """Verify's own writes, uncommitted at the converged gate, stay inside the verify envelope."""
    root, change = product_at("implemented")
    import sys

    put(root, f"{OLD}/verification.md", "# Change Verification\n\n- Outcome: `converged`\n")
    cli("evidence", change, "--phase", "verification", "--", sys.executable, "tests/test_banner.py")
    cli("state", change, "--task", "TASK-001", "--status", "verified")
    cli("advance", change, "--gate", "converged")
    code, data = leash(root)
    assert code == 0 and data["violations"] == [], data
    assert commit(root, "verify", verify=True).returncode == 0

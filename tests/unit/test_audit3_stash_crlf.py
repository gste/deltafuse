"""A Writer-written file git gave back with CRLF is still the Writer's (audit 3, B's stash case).

Auditor B: after `git stash -u` and `git stash pop` mid-Change, the leash called the Writer-written
`routing.yaml` and `slices/SLICE-01.md` "written by hand" although their receipts were there.
Reproduced on a copy of audit3/B/p1: under `core.autocrlf=true` the stash keeps the untracked
files as LF blobs and the pop checks them out with CRLF; the receipt's sha256 is of the LF bytes
the Writer wrote. The same happens to any checkout of such a file on a Windows clone. The
vouching digest is now taken line-ending-normalized, as the oracle, the base revision and the
spec acceptance already are.
"""

from __future__ import annotations

from tests.fixtures.leash_walk import (  # noqa: F401 - fixtures
    CHANGE, git, leash, product_at, walk, write,
)


def _analyze_written_uncommitted(product_at):
    root, change = product_at("intake")
    write(root, "routing", {"identity": "routing", "fields": {"route": "code", "claims": {
        "CR-001": {"summary": "Banner on start", "primary_capability": "system.core",
                   "related_capabilities": [], "policies": [], "confidence": "high"}}}})
    write(root, "slice", {"identity": "SLICE-01", "fields": {
        "title": "Banner", "primary_capability": "system.core", "claims": ["CR-001"],
        "spec_refs": ["docs/spec/core.md"]}, "body": "Print a banner on start."})
    return root, change


def _stash_round_trip_with_autocrlf(root) -> None:
    git(root, "config", "core.autocrlf", "true")
    git(root, "stash", "push", "-u", "-q")
    git(root, "stash", "pop", "-q")


def test_a_stash_round_trip_keeps_the_writers_files_the_writers(product_at):
    root, change = _analyze_written_uncommitted(product_at)
    _stash_round_trip_with_autocrlf(root)
    assert b"\r\n" in (change / "routing.yaml").read_bytes()  # the case: CRLF came back
    code, data = leash(root)
    hand = [v for v in data.get("violations", []) if "written by hand" in v]
    assert hand == [], data
    assert code == 0, data


def test_a_hand_edit_after_the_round_trip_is_still_one(product_at):
    """The twin: line endings are forgiven, content is not."""
    root, change = _analyze_written_uncommitted(product_at)
    _stash_round_trip_with_autocrlf(root)
    slice_file = change / "slices" / "SLICE-01.md"
    slice_file.write_bytes(slice_file.read_bytes().replace(b"Print a banner", b"Print two banners"))
    code, data = leash(root)
    assert any("SLICE-01.md" in v and "written by hand" in v for v in data.get("violations", [])), data

"""Two catalog rules from the Fuse-Back decision (q6 5(a) and 5(b)), bounded by q8.

(a) `code_roots` of `active` capabilities do not overlap: the under-routing
    detector maps a diff to owners through them.
(b) With `project.baseline: accepted`, a Change is not routed into a `draft`
    capability whose `code_roots` hold code nobody has characterized. A draft with
    no code there - the new capability q8 lets a Worker propose - is not touched.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from deltafuse.core.config import validate_active_code_roots, validate_config
from deltafuse.core.fsm import _uncharacterized_draft_errors


def _product(tmp_path: Path, capabilities: dict, *, baseline: str = "accepted") -> Path:
    (tmp_path / ".deltafuse").mkdir()
    (tmp_path / ".deltafuse" / "config.yaml").write_text(
        yaml.safe_dump({"schema_version": 3, "project": {"baseline": baseline}}), encoding="utf-8"
    )
    (tmp_path / "docs" / "spec").mkdir(parents=True)
    catalog = {"schema_version": 3, "domains": {"core": {"summary": "core", "capabilities": capabilities}}}
    (tmp_path / "docs" / "spec" / "_capabilities.yaml").write_text(yaml.safe_dump(catalog), encoding="utf-8")
    return tmp_path


def _cap(status: str, *roots: str) -> dict:
    return {
        "summary": "x",
        "spec": ["docs/spec/core/x.md"],
        "code_roots": list(roots),
        "status": status,
        "type": "supporting",
    }


def _routed_to(product: Path, *capabilities: str) -> Path:
    change = product / "docs" / "changes" / "CHG-001"
    change.mkdir(parents=True)
    claims = {
        f"CR-{i:03d}": {"primary_capability": cap, "related_capabilities": []}
        for i, cap in enumerate(capabilities, 1)
    }
    (change / "routing.yaml").write_text(yaml.safe_dump({"claims": claims}), encoding="utf-8")
    return change


# --- rule (a) ---------------------------------------------------------------


def test_active_capabilities_sharing_a_root_are_refused(tmp_path: Path):
    product = _product(
        tmp_path,
        {"a": _cap("active", "src/ratelimit"), "b": _cap("active", "src/ratelimit/policy")},
    )
    errors = validate_active_code_roots(product)
    assert len(errors) == 1
    assert "core.a" in errors[0] and "core.b" in errors[0] and "disjoint" in errors[0]
    # ...and `validate-config` reports it, which is where Fuse-Back's handoff asks.
    assert any("overlap in code_roots" in e for e in validate_config(product))


def test_the_same_root_twice_and_roots_that_only_share_a_name_prefix_are_fine(tmp_path: Path):
    product = _product(
        tmp_path,
        {
            "a": _cap("active", "src/ratelimit", "src/ratelimit/"),  # one capability, two spellings
            "b": _cap("active", "src/ratelimit_extra"),  # `src/ratelimit` is not a directory prefix of it
            "c": _cap("active", "src/other/**"),
        },
    )
    assert validate_active_code_roots(product) == []


def test_only_active_capabilities_count(tmp_path: Path):
    """A partial adoption must not be blocked by drafts, nor by retired capabilities."""
    product = _product(
        tmp_path,
        {
            "a": _cap("active", "src/ratelimit"),
            "b": _cap("draft", "src/ratelimit"),
            "c": _cap("deprecated", "src/ratelimit"),
            "d": _cap("removed", "src/ratelimit"),
        },
    )
    assert validate_active_code_roots(product) == []


def test_a_missing_catalog_is_not_this_rules_error(tmp_path: Path):
    (tmp_path / ".deltafuse").mkdir()
    assert validate_active_code_roots(tmp_path) == []


# --- rule (b), D7 ------------------------------------------------------------


def test_a_draft_holding_inherited_code_halts_the_change_once_the_baseline_is_accepted(tmp_path: Path):
    product = _product(tmp_path, {"legacy": _cap("draft", "src/legacy")})
    (product / "src" / "legacy").mkdir(parents=True)
    (product / "src" / "legacy" / "mod.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    change = _routed_to(product, "core.legacy")
    errors = _uncharacterized_draft_errors(change, product)
    assert len(errors) == 1
    assert "core.legacy" in errors[0] and "characterize" in errors[0]


def test_a_draft_with_no_code_is_the_q8_proposal_and_is_not_stopped(tmp_path: Path):
    """The Worker proposed it in Analyze (q8); the human accepts it at `specified`."""
    product = _product(tmp_path, {"stats": _cap("draft")})  # no code_roots at all
    change = _routed_to(product, "core.stats")
    assert _uncharacterized_draft_errors(change, product) == []

    # A proposal may name the directory it means to create; nothing is there yet.
    second = tmp_path / "second"
    second.mkdir()
    product2 = _product(second, {"stats": _cap("draft", "src/monitoring")})
    change2 = _routed_to(product2, "core.stats")
    assert _uncharacterized_draft_errors(change2, product2) == []


def test_while_the_baseline_is_draft_nothing_is_stopped(tmp_path: Path):
    """The Bootstrap profile writes the first spec over existing code."""
    product = _product(tmp_path, {"legacy": _cap("draft", "src/legacy")}, baseline="draft")
    (product / "src" / "legacy").mkdir(parents=True)
    (product / "src" / "legacy" / "mod.py").write_text("x = 1\n", encoding="utf-8")
    change = _routed_to(product, "core.legacy")
    assert _uncharacterized_draft_errors(change, product) == []


def test_an_active_capability_with_code_is_not_stopped(tmp_path: Path):
    product = _product(tmp_path, {"legacy": _cap("active", "src/legacy")})
    (product / "src" / "legacy").mkdir(parents=True)
    (product / "src" / "legacy" / "mod.py").write_text("x = 1\n", encoding="utf-8")
    change = _routed_to(product, "core.legacy")
    assert _uncharacterized_draft_errors(change, product) == []


def test_a_direct_root_and_the_directory_below_it_do_not_overlap(tmp_path: Path):
    """q6 `dir/*`: markdown/* (the core) beside markdown/extensions/ (the extensions)."""
    product = _product(
        tmp_path,
        {"core": _cap("active", "markdown/*"), "extensions": _cap("active", "markdown/extensions/")},
    )
    assert validate_active_code_roots(product) == []
    assert not any("code_roots" in e for e in validate_config(product))


def test_a_direct_root_still_overlaps_its_own_directory_and_itself(tmp_path: Path):
    for i, (first, second) in enumerate((("markdown/*", "markdown/"), ("markdown/*", "markdown/*"))):
        sub = tmp_path / f"pair{i}"
        sub.mkdir()
        product = _product(sub, {"a": _cap("active", first), "b": _cap("active", second)})
        assert len(validate_active_code_roots(product)) == 1, (first, second)
    # a direct root of a parent directory owns nothing in the child: no overlap
    other = tmp_path / "other"
    other.mkdir()
    product = _product(other, {"a": _cap("active", "pkg/*"), "b": _cap("active", "pkg/sub/*")})
    assert validate_active_code_roots(product) == []
    # while a recursive root above a direct one does contain it
    third = tmp_path / "third"
    third.mkdir()
    product = _product(third, {"a": _cap("active", "pkg/"), "b": _cap("active", "pkg/sub/*")})
    assert len(validate_active_code_roots(product)) == 1


def test_a_draft_with_a_direct_root_over_files_halts_and_over_nothing_does_not(tmp_path: Path):
    product = _product(tmp_path, {"legacy": _cap("draft", "src/legacy/*")})
    (product / "src" / "legacy" / "sub").mkdir(parents=True)
    # only a file in a subdirectory: the direct root owns none of it
    (product / "src" / "legacy" / "sub" / "deep.py").write_text("x = 1\n", encoding="utf-8")
    change = _routed_to(product, "core.legacy")
    assert _uncharacterized_draft_errors(change, product) == []
    (product / "src" / "legacy" / "mod.py").write_text("x = 1\n", encoding="utf-8")
    errors = _uncharacterized_draft_errors(change, product)
    assert len(errors) == 1 and "src/legacy/*" in errors[0]
    # an empty directory (the q8 proposal) is not stopped
    second = tmp_path / "second"
    second.mkdir()
    product2 = _product(second, {"stats": _cap("draft", "src/monitoring/*")})
    (product2 / "src" / "monitoring").mkdir(parents=True)
    assert _uncharacterized_draft_errors(_routed_to(product2, "core.stats"), product2) == []

# Acceptance tests for S11: concurrent Changes on a shared spec, then deletion.
# Hidden from the executing model. change_data is assembled by the A09 harness.


def test_stale_evidence_rejected_after_merge(change_data):
    merge = change_data.get("after_merge", {})
    stale_passed = merge.get("stale_green_accepted", False)
    assert stale_passed is False, "Stale Green evidence from pre-merge baseline passed converged"


def test_evidence_rerun_or_invalidated(change_data):
    merge = change_data.get("after_merge", {})
    invalidated = merge.get("evidence_invalidated", False)
    rerun = merge.get("evidence_rerun", False)
    assert invalidated or rerun, "Merged CHG-B kept pre-merge evidence without invalidation or rerun"


def test_merged_spec_has_both_live_claims(change_data):
    spec_text = change_data.get("spec_text", "")
    assert "get_window_stats" in spec_text or "window_stats" in spec_text, \
        "CHG-B stats claim missing from merged spec"
    burst_expected = change_data.get("burst_still_required", True)
    if burst_expected:
        assert "burst_allowance" in spec_text, "Landed CHG-A burst claim missing from merged spec"


def test_deletion_removes_burst(change_data):
    after = change_data.get("after_deletion", {})
    for surface in ("spec_text", "code_text", "test_text", "catalog_text"):
        text = after.get(surface, "")
        assert "burst_allowance" not in text, f"burst_allowance leftover in {surface}"


def test_no_dangling_spec_refs(change_data):
    dangling = change_data.get("after_deletion", {}).get("dangling_refs", [])
    assert dangling == [], f"Deletion left dangling spec/catalog refs: {dangling}"

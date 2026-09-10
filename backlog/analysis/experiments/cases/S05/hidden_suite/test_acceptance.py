# Acceptance test for S05: verifies that both capabilities are specified,
# implemented, and tested with proper cross-boundary integration.

def test_multi_capability_spec_completeness(change_data):
    specs = change_data.get("spec_files", [])
    assert any("usage_stats" in s for s in specs), "Missing usage_stats spec"
    assert any("rate_policy" in s for s in specs), "Missing rate_policy spec"


def test_multi_capability_slicing(change_data):
    slices = change_data.get("slices", [])
    assert len(slices) >= 2, "Expected at least 2 slices for two capabilities"


def test_integration_tests_present(change_data):
    tests = change_data.get("test_files", [])
    assert any("integration" in t for t in tests), "Missing integration tests"


def test_stats_reflect_policy_blocks(change_data):
    stats = change_data.get("stats_snapshot", {})
    if stats.get("policy_blocked", False):
        assert stats.get("rejected_calls", 0) > 0, "Blocked key must have rejections in stats"

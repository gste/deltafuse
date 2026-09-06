# Acceptance test for S08a: verifies proportionate routing for refactoring
# and that spec remains unchanged when no behavioral change occurs.

def test_spec_unchanged(change_data):
    spec_changes = change_data.get("spec_modifications", [])
    ratelimit_spec = [s for s in spec_changes if "ratelimit" in s]
    assert len(ratelimit_spec) == 0, "Spec must not change for pure refactoring"


def test_proportionate_route(change_data):
    route = change_data.get("routing", {})
    route_type = route.get("type", "")
    assert route_type in ("refactoring", "structural"), \
        f"Expected refactoring/structural route, got {route_type}"


def test_existing_tests_pass(change_data):
    test_results = change_data.get("test_results", {})
    failures = test_results.get("failures", 0)
    assert failures == 0, f"Existing tests must pass after refactoring, got {failures} failures"


def test_no_fictitious_red(change_data):
    red_evidence = change_data.get("red_evidence", [])
    behavioral_reds = [r for r in red_evidence if r.get("type") == "behavioral"]
    assert len(behavioral_reds) == 0, "Pure refactoring must not generate fictitious behavioral Red"

# Acceptance test for S08c: operational change must not touch code, spec, or tests.

def test_no_code_changes(change_data):
    code_changes = change_data.get("code_modifications", [])
    assert len(code_changes) == 0, "Operational change must not modify code"


def test_no_spec_changes(change_data):
    spec_changes = change_data.get("spec_modifications", [])
    assert len(spec_changes) == 0, "Operational change must not modify spec"


def test_no_test_changes(change_data):
    test_changes = change_data.get("test_modifications", [])
    assert len(test_changes) == 0, "Operational change must not modify tests"


def test_operational_route(change_data):
    route = change_data.get("routing", {})
    route_type = route.get("type", "")
    assert route_type in ("operational", "infra", "ops"), \
        f"Expected operational route, got {route_type}"

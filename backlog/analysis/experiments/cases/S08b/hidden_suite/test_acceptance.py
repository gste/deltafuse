# Acceptance test for S08b: docs-only change must not touch code or tests.

def test_no_code_changes(change_data):
    code_changes = change_data.get("code_modifications", [])
    assert len(code_changes) == 0, "Docs-only change must not modify code files"


def test_no_test_changes(change_data):
    test_changes = change_data.get("test_modifications", [])
    assert len(test_changes) == 0, "Docs-only change must not modify test files"


def test_docs_route_type(change_data):
    route = change_data.get("routing", {})
    route_type = route.get("type", "")
    assert route_type in ("docs", "documentation"), \
        f"Expected docs route, got {route_type}"


def test_no_red_green_cycle(change_data):
    red_evidence = change_data.get("red_evidence", [])
    green_evidence = change_data.get("green_evidence", [])
    assert len(red_evidence) == 0, "Docs-only must not have Red phase"
    assert len(green_evidence) == 0, "Docs-only must not have Green phase"

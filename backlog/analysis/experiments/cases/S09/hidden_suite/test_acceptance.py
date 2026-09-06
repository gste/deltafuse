# Acceptance test for S09: terminal outcomes with provenance.

def test_change_rejected(change_data):
    status = change_data.get("status", "")
    assert status in ("rejected", "duplicate", "closed"), \
        f"Expected terminal status, got {status}"


def test_provenance_refs(change_data):
    refs = change_data.get("provenance_refs", [])
    ref_str = " ".join(refs)
    assert "CHG-042" in ref_str, "Missing reference to rejected CHG-042"
    assert "CHG-060" in ref_str or "CHG-055" in ref_str, "Missing supersession reference"


def test_no_implementation(change_data):
    code_changes = change_data.get("code_modifications", [])
    assert len(code_changes) == 0, "Rejected change must not produce code"


def test_no_spec_changes(change_data):
    spec_changes = change_data.get("spec_modifications", [])
    assert len(spec_changes) == 0, "Rejected change must not modify spec"

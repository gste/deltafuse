# Acceptance test for S06: verifies bounded intake with noisy input
# and complete coverage of substantive claims.

def test_claims_extracted_from_noise(change_data):
    claims = change_data.get("claims", [])
    claim_ids = [c.get("id") for c in claims]
    assert "CR-001" in claim_ids, "Missing audit log claim"
    assert "CR-002" in claim_ids, "Missing alert claim"


def test_no_phantom_claims_from_noise(change_data):
    claims = change_data.get("claims", [])
    for c in claims:
        title = c.get("title", "").lower()
        assert "internal_gc" not in title, "Phantom claim from DEBUG noise"
        assert "network retransmit" not in title, "Phantom claim from WARN noise"


def test_audit_log_rotation_specified(change_data):
    specs = change_data.get("spec_content", {})
    audit_spec = specs.get("monitoring.audit_log", "")
    assert "rotation" in audit_spec.lower() or "10" in audit_spec, "Missing rotation spec"


def test_alert_fields_complete(change_data):
    specs = change_data.get("spec_content", {})
    audit_spec = specs.get("monitoring.audit_log", "")
    for field in ["window_start", "window_end", "rejection_count", "threshold"]:
        assert field in audit_spec or field in str(change_data), f"Missing alert field: {field}"

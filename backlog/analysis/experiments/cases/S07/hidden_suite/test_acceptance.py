# Acceptance test for S07: verifies correct routing in large catalog
# and proper slicing of oversized capability without hidden full reads.

def test_routing_targets_correct_capability(change_data):
    routing = change_data.get("routing", {})
    primary = routing.get("primary_capability", "")
    assert "distributed_ratelimit" in primary, "Must route to infra.distributed_ratelimit"


def test_existing_capabilities_unmodified(change_data):
    modified_caps = change_data.get("modified_capabilities", [])
    allowed = {"infra.distributed_ratelimit", "security.ratelimit",
               "infra.config_reload", "monitoring.health_check"}
    for cap in modified_caps:
        assert cap in allowed, f"Unexpected modification to existing capability: {cap}"


def test_slicing_bounded(change_data):
    slices = change_data.get("slices", [])
    assert 1 <= len(slices) <= 3, f"Expected 1-3 slices, got {len(slices)}"


def test_no_hidden_full_catalog_read(change_data):
    reads = change_data.get("file_reads", [])
    cap_reads = [r for r in reads if "_capabilities.yaml" in r]
    # Should read catalog once for routing, not iterate all 15 spec files
    non_target_reads = [r for r in reads if "billing" in r or "api.pagination" in r]
    assert len(non_target_reads) == 0, "Hidden full catalog read detected"

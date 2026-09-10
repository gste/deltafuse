# Acceptance test for S04 checks that the FSM properly halts at blocked-on-decision
# and generates a formal ADR proposal without modifying code or specs prematurely.

def test_ambiguity_gating_and_decision_creation(change_data):
    assert change_data.get("status") == "blocked-on-decision"
    decisions = change_data.get("decisions", [])
    assert len(decisions) >= 1
    dec_ref = decisions[0]
    assert "DEC-" in dec_ref
    # Verify no unapproved code or spec modifications exist
    deltas = change_data.get("deltas", [])
    assert len(deltas) == 0 or all(d.get("status") == "proposed" for d in deltas)

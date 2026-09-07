---
change: CHG-001-ratelimit-consume-history
status: accepted
slices:
  - SLICE-01
added:
  - REQ-RL-05
  - REQ-RL-06
  - REQ-RL-07
  - REQ-RL-08
modified: []
removed: []
---

# Specification Delta — CHG-001-ratelimit-consume-history

Slice SLICE-01: Record consume() events and expose get_history(key, n)

## ADDED

- REQ-RL-05: Every call to consume(key, tokens) MUST record an immutable event containing the key, the moment in time, the requested token count, and the outcome (accepted or rejected).
- REQ-RL-06: get_history(key, n=10) MUST return the last n events for the given key, newest first.
- REQ-RL-07: The parameter n MUST be an integer >= 1. An invalid n MUST raise an exception.
- REQ-RL-08: History recording MUST NOT change the semantics of consume (REQ-RL-02/03). Records for different keys MUST NOT be mixed.

## MODIFIED

- None.

## REMOVED

- None.

## Notes

- REQ-RL-05 through REQ-RL-08 were added to docs/spec/security/ratelimit.md to mirror accepted claims CR-002, CR-003, CR-004, CR-005, CR-006. Baseline requirements REQ-RL-01 through REQ-RL-04 are unchanged and remain the normative baseline for consume semantics.

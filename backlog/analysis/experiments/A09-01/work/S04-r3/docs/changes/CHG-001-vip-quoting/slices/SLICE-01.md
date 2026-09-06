# SLICE-01: VIP rate-limit exemption mechanism

- primary_capability: security.ratelimit
- claims: [CR-001, CR-002, CR-003, CR-004, CR-005, CR-006]
- status: blocked

## Open Fork

CR-002 allows the implementer to choose one of three mutually exclusive
mechanisms for exempting VIP users from general limits:

1. effectively infinite quota
2. separate, enlarged token pool (~10x normal quota)
3. out-of-order priority service

CR-003 confirms the request does not mandate any single approach. Exactly one
must be selected by a human via DEC-0001 before this slice can proceed.

## Dependencies

- CR-005 (definition of "VIP") and CR-006 (current quota model / extension
  points) remain unresolved and must be discovered during specification.

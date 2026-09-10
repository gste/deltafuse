# Request: Add IPv6 support to security.ip_filter (S09)

## Summary

The user requested adding IPv6 address support to the `security.ip_filter` capability
(`docs/intake/S09.md`). Analysis of the intake indicates this request is a duplicate of
CHG-042 (rejected a month ago by the architectural committee because the current
infrastructure does not support IPv6; the network stack must be updated first via INFRA-789,
status: not-started). An analogous alternative request CHG-055 was superseded by CHG-060,
which includes a full rewrite of `ip_filter` with CIDR notation support. The request cannot
be reproduced in the current environment because the IPv6 test stand is disabled.

Expected outcome: justified closure with explicit provenance (references to CHG-042,
CHG-055, CHG-060, INFRA-789).

## Claims

- CR-001 [observation]: The user asked to add IPv6 address support to capability `security.ip_filter`.
- CR-002 [observation]: The request is a duplicate of CHG-042, which was rejected a month ago by the architectural committee.
- CR-003 [observation]: CHG-042 was rejected on the grounds that the current infrastructure does not support IPv6 and the network stack must first be updated (task INFRA-789, status: not-started).
- CR-004 [observation]: An analogous alternative request CHG-055 was superseded by CHG-060, which includes a full rewrite of `ip_filter` with CIDR notation support.
- CR-005 [observation]: The request cannot be reproduced in the current environment because the IPv6 test stand is disabled.
- CR-006 [expectation]: The expected result is a justified closure with explicit provenance referencing CHG-042, CHG-055, CHG-060, and INFRA-789.

## Unknowns

- The exact current status of INFRA-789 is not verified against product records (only as stated in the intake).
- Whether CHG-060's CIDR rewrite already covers IPv6 is not confirmed from the specification (spec not read).

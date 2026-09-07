---
id: SLICE-01
change: CHG-061-ipv6-ip-filter
title: Closure with provenance
status: analyzed
primary_capability: change-management
related_capabilities:
  - security.ip_filter
claims:
  - CR-001
  - CR-002
  - CR-003
  - CR-004
  - CR-005
spec_refs:
  - docs/spec/security/ip_filter.md
context_budget:
  max_tokens: 2000
  max_files: 6
---

## Scope

- In scope: classify the request, establish provenance, recommend closure.
- Out of scope: any capability delta to `security.ip_filter`.

## Slices

### Slice 1 — Classification and provenance

- **Claims:** CR-001, CR-002, CR-003, CR-004, CR-005.
- **Primary capability:** change-management (related: security.ip_filter).
- **Outcome:** Request is a duplicate of rejected CHG-042, superseded by CHG-060; IPv6 explicitly out of scope per REQ-IP-01; cannot be reproduced (test stand disabled). No capability work required.
- **Spec refs:** `docs/spec/security/ip_filter.md` (REQ-IP-01: IPv6 out of scope until network stack upgrade).
- **Unchanged behavior:** `security.ip_filter` IPv4-only behavior remains the accepted baseline; no spec/catalog/Decision delta.
- **Risks:** None material; provenance chain is self-consistent.
- **Context budget:** ~2000 tokens, 6 files.

## Delta projection

| Artifact | Operation |
|---|---|
| Specification | none |
| Catalog | none |
| Decisions | none (closure is change-management action) |
| Tasks | none |
| Tests | none |
| Implementation | none |
| Evidence | record provenance (CHG-042, CHG-055, CHG-060, INFRA-789) |

## Notes

All claims routed to change-management; no capability delta. Recommend `/specify-change CHG-061-ipv6-ip-filter SLICE-01` for closure decision.

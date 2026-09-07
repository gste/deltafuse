---
change: CHG-061-ipv6-ip-filter
status: unchanged
slices:
  - SLICE-01
---

# spec-delta — CHG-061-ipv6-ip-filter

## Summary

No normative specification change. `security.ip_filter` IPv4-only behavior
remains the accepted baseline. REQ-IP-01 already states IPv6 is out of scope
until the network stack is upgraded.

## Delta

- ADDED: none
- MODIFIED: none
- REMOVED: none

## Proofs of sufficiency

- `docs/spec/security/ip_filter.md` REQ-IP-01 already covers IPv4 acceptance and
  explicitly excludes IPv6 until the network stack upgrade. The accepted spec is
  sufficient; no capability catalog or Decision delta is required.

---
id: DEC-0001-vip-quoting-mechanism
title: VIP rate-limiting mechanism and VIP identification
kind: product
status: proposed
owner: engineering
date: 2025-01-01
change: CHG-001-vip-quoting
affects:
  capabilities:
    - ratelimit
  spec_refs:
    - docs/spec/security/ratelimit.md
---

## Status

Proposed. Not accepted; awaiting a human Decision.

## Context

CR-002 requires VIP users to escape the general rate limits, and CR-003 lists
several candidate mechanisms while CR-004 defers the choice to the team. CR-005
notes that neither the VIP identification method nor the baseline quota value is
specified.

## Decisions

1. **Mechanism (unresolved options):** choose one of (a) an effectively infinite
   quota for VIP users, (b) a separate enlarged token pool (e.g. 10x the normal
   amount), or (c) out-of-order priority servicing for VIP users.
2. **VIP identification (unresolved options):** identify VIP status via account
   flag, subscription tier, API key class, or another mechanism.
3. **Baseline quota (unresolved):** define the "normal" quota value that any
   multiplier would apply to.

## Consequences

Until these choices are made the slice cannot be specified or implemented with a
verifiable outcome, so analysis is blocked pending a human Decision.

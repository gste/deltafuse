# Spec Delta — CHG-001-usage-stats-and-rate-policy

Slice: SLICE-01
Status: proposed

## ADDED

### docs/spec/monitoring/usage_stats.md

New normative capability spec `monitoring.usage_stats` with requirement IDs:

- **REQ-US-01 Per-key counters** — track per key: total `consume` calls, successful calls, rejected calls (rejection = any `consume` returning `False`, from token shortage or policy block).
- **REQ-US-02 Peak load** — track peak load per key as the maximum number of `consume` calls in any single one-second window.
- **REQ-US-03 get_stats** — `get_stats(key)` returns a dict with total calls, successful calls, rejected calls, and peak load for the key.
- **REQ-US-04 Rejection accounting** — stats reflect rejections from both token shortage and policy blocking without double-counting a single `consume` call.

## MODIFIED

- None.

## REMOVED

- None.

## Catalog

- Added `monitoring` domain and `usage_stats` capability entry in `docs/spec/_capabilities.yaml`.

## Decisions

- None blocking. Illustrative values (threshold 50, default block 300s) are configurable parameters, not Decisions.
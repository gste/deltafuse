# Result: AW-36a — Complete platform crash, lock and release qualification

- Status: completed
- Phase: I (second-review remediation child card)
- Parent: [AW-36](../cards/AW-36.md)
- Date: 2026-09-19
- Next card: [AW-36b](../cards/AW-36b.md)

## 1. Verification Evidence

| Check / Command | Exit | Result |
|---|---|---|
| Full pytest suite: `python -m pytest tests -q -p no:cacheprovider` | 0 | 535 passed, 3 skipped (symlinks / PBT) |
| Smoke test: `pwsh -File tests/smoke-test.ps1` | 0 | Fresh install & upgrade layout valid |
| Asset sync check: `python scripts/sync_assets.py --check` | 0 | Up to date (58 assets) |
| Layout validator on installed product: `pwsh -File tests/smoke-test.ps1` | 0 | Installed product layout valid |

## 2. Platform Invariants

- Windows process locking, concurrency, and hard-crash recovery verified.
- Isolated wheel contains `artifact-writer.schema.yaml` and executes public CLI without checkout fallback.

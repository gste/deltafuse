# AW-42 reconciliation evidence bundle

Retained raw evidence for `results/AW-42.md`. Everything referenced here is inside
this repository — there is no external preserved-run indirection.

Index: `bundle-index.json` (SHA256 of every bundled file, tested-source identity, both
environment records, and a recorded exit for each executed check). It deliberately
omits itself, `hash-reconciliation.json` and `source-inventory.json`: those three are
derived reports, and indexing them would make the index and the inventory digest each
other and never settle. Their digests are published in `results/AW-42.md`, which sits
outside this bundle.

## Contents

| File | What it is |
|---|---|
| `reconcile_hashes.py` | Recomputes every `ref -> sha256` claim found in tracked reports and evidence manifests and classifies each as match / drift / line-ending-only / unresolved / external. Exits 1 when any final-scope claim is unverified. |
| `hash-reconciliation.json` | Its output: 316 claims, split into `final_scope` (176 — cards AW-37..AW-45, the AW-40 evaluation index, both predecessor manifests, and this bundle's own index) and `historical_record` (140 — cards AW-00..AW-36), each with `claim_kind`. |
| `inventory_source.py` | Whole-tree inventory: 498 tracked files plus untracked bundle files, worktree SHA256, HEAD blob id, and both raw and CRLF-normalized comparisons. |
| `source-inventory.json` | Its output, including per-scope aggregate digests. |
| `run_checks.py` | Drives the nine Windows-side checks, capturing argv, exit, stdout and stderr. |
| `check-index.json` | Commands, exits, environment and raw-log digests for that run. |
| `posix_rerun.sh` | Native Ubuntu-24.04 re-qualification: copies the final tree onto ext4, builds a venv, runs the concurrency / crash / locking / security / CLI suites, the Writer unit suites, `tests/smoke-test.sh`, and a symlink capability probe. |
| `probe_pointer_escaping.py` | Separates pointer-escaping *behaviour* from pointer-escaping *coverage*, and reports how many committed assertions use an escaped pointer literal. |
| `write_bundle_index.py` | Builds `bundle-index.json`. |
| `baseline-AW-42-result.md` | The superseded `results/AW-42.md` kept byte-for-byte so its 15 digest claims stay inspectable against the tree that produced them. |
| `raw/` | One `.log` and one `.exit` per executed check, plus the wheel build and identity transcripts. Four observational transcripts carry no exit because none was captured at run time; they are named in `bundle-index.json` under `observational_logs_without_exit` rather than given an invented code. |

## Re-verifying

```
python reconcile_hashes.py --repo <checkout> --out /tmp/recon.json
python inventory_source.py --repo <checkout> --out /tmp/inv.json
python probe_pointer_escaping.py
python run_checks.py --repo <checkout>
wsl.exe -d Ubuntu-24.04 -- bash <checkout>/backlog/schema-driven-artifact-writer/\
evidence/reconciliation/AW-42/posix_rerun.sh
```

`run_checks.py` and `posix_rerun.sh` overwrite `raw/` and `check-index.json` and then
`write_bundle_index.py` must be re-run; the committed digests in `bundle-index.json`
describe the run recorded in `results/AW-42.md`, not a later re-execution.

## Two caveats a reader should not miss

1. `AW-41` and `AW-44` reference raw logs that are **not** in the repository. This
   bundle does not stand in for them; it re-executes the same operations and keeps
   those logs here. The predecessor records still need their own repair.
2. `dist/` and `build/aw42-wheel/` both contain a wheel named
   `deltafuse-3.1.0-py3-none-any.whl` with different digests. Neither is AW-44's
   recorded build, and two builds of one tree differ here anyway, so a wheel digest
   is not usable as final-tree identity. Bind to source digests instead.
   `build/aw42-wheel/` is a gitignored throwaway created by this card.

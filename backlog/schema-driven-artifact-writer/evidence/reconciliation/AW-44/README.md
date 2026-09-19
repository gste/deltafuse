# AW-44 evidence bundle — real isolated-wheel qualification rerun (2026-09-19)

This directory is the portable hash-indexed evidence index for AW-44. The raw
artifacts (full argv/stdout/stderr logs, build wheel, venv, manifests) live in
the preserved run location referenced as `<preserved-run-location>/aw44-evidence-20260919`
and are hash-indexed by `MANIFEST.json`. This index contains portable refs and
digests only — no machine-specific absolute paths or credentials.

## What was executed (all on the 2026-09-19 rerun)

- `python scripts/sync_assets.py --check` — exit 0 (58 assets in sync).
- `python -m pip wheel --no-deps -w <dist> <repo-checkout>` — real wheel
  `deltafuse-3.1.0-py3-none-any.whl`, SHA256
  `8cad283574d44d17787b559557385e053a731b523839920d505fa980c41c434d`.
- Fresh `venv` created with pip; `pip install -I <wheel>` — exit 0; installed
  dependencies recorded in MANIFEST (attrs, jsonschema, PyYAML, referencing,
  rpds-py; deltafuse 3.1.0).
- Import-origin probe: `deltafuse` resolves inside the isolated venv
  site-packages; the checkout root is excluded from the import path.
- Intact `artifact describe` through the installed wheel CLI — exit 0.
- Regression: `python -m pytest tests/integration/test_artifact_cli.py
  tests/integration/test_wheel_smoke.py tests/integration/test_wheel_evidence.py
  -v -s` — **16 passed, exit 0** (raw log `raw/final-s.log`).

## Strengthened probe (AW44-R3)

`tests/integration/test_artifact_cli.py::test_isolated_wheel_packaged_schema_removal_and_corruption`
now also asserts, in addition to exit code 5 / `asset_resolution_failed` /
unchanged product bytes:

- physically removing the installed `artifact-writer.schema.yaml` denies
  `artifact create` (exit 5) with no artifact and **no new journal/receipt
  records** under the product `.deltafuse/journal` and `.deltafuse/receipts`;
- separately corrupting the schema bytes without manifest repair denies both
  `create` (TASK-202) and `update` (TASK-201) with unchanged product bytes and
  **no new journal/receipt records**; exact schema bytes are restored and
  digest-verified between probes and in `finally`.
- intact describe/validate controls still pass after restoration.

Missing/absent raw evidence is NOT invented: the pre-2026-09-19 claims that
"full pytest suite passed exit 0" remain dated historical claims in
`results/AW-41.md`; this bundle evidences the wheel-scoped rerun only.

## Still open (owned by other cards — this bundle does not waive them)

- AW-41 R3/F1: native POSIX concurrency/hard-crash and capable-host
  symlink/reparse execution (requires a real POSIX host / privileges).
- AW-40 R2/F1: live paired small-model sessions (requires an authorized
  endpoint).

## Re-verification

At the preserved location: `python driver.py` re-executes the build/install/
origin/digest steps and rewrites `raw/driver-run.json` + `manifest.json`;
compare every digest in this index against the on-disk bytes (all referenced
files are retrievable by name in the preserved location).
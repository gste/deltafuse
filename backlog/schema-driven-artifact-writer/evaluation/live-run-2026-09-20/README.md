# Live paired-model run — 2026-09-20 (executed, delivery-verified)

> **Retracted verdict:** an earlier revision of this file (commit 0482b1e)
> concluded the endpoint was "functionally unsuitable" and that the measured
> run could not be executed. That conclusion was premature: it was made
> without verifying prompt delivery at the child-process boundary. The
> observability-extension probe in `../delivery-probe-2026-09-20/` proved the
> frozen `little-coder` `.CMD`/cmd.exe transport silently truncated every
> multiline `-p` prompt to its first line, so the model never received the
> requested values. See spec AMEND-3. The `pilot-raw/` and `probe-unsuitable/`
> traces below are retained as superseded, delivery-confounded evidence.

## Purpose

AW-40 requires actual fresh manual-arm (A) and Writer-arm (B) model sessions
with a real, fixed model identity, preregistered protocol, immutable raw
traces, and metrics replayed from those traces. This directory records the
executed run on `little-coder` → `inclusionai/ling-3.0-flash-fin:free`.

## Frozen preregistration

- `spec.json` — frozen parameters (model identity, corpus, arms, budget of 3
  attempts per case/arm, counterbalanced arm order, stopping rule, success
  criterion, uncertainty method) written BEFORE any outcome collection.
- AMEND-1 (explicit `--system-prompt` override), AMEND-2 (short user prompts;
  superseded by AMEND-3), AMEND-3 (delivery-verified node-direct neutral-cwd
  transport with per-call byte-verification; recorded before any valid
  measured collection).

## Run and metrics (from `raw/` traces only; see `summary.json`)

- 8 cases × 2 arms; 28 attempt traces; every call `delivery_verified=true`
  (observability-extension captured user message byte-identical to the
  intended prompt); 0 infra-invalid retries.
- **Arm A (manual raw YAML):** first-pass valid 2/8 = 25.0% (Clopper-Pearson
  95% CI 3.19–65.09), semantic 25.0%, 12 mechanical retries; all 5 positive
  strata failed structural/schema validation within the 3-attempt budget;
  forbidden-gate demonstration 0/1 (CASE-08 rejected only at schema level).
- **Arm B (typed Writer):** first-pass valid 8/8 = 100% (CI 63.06–100),
  semantic 100%, 0 mechanical retries; defense cases rejected by the Writer
  with exact reason codes ([required_property_missing], [schema_validation_failed],
  [core_owned_field]); forbidden gate blocked 1/1; no disk mutation on denial.
- EXPLORATORY (n=8 per arm): reported as observation; no general
  model-gain claim; denominator integrity preserved.

## Raw traces

- `raw/*.json` — measured run, 28 traces (prompt, argv, child_cwd,
  captured_prompt, delivery_verified, exit, full model output, verdict).
- `pilot-raw-amend3/` (parent dir) — corrected-transport pilot, 8 traces,
  all delivery_verified, model reproduces requested values.
- `pilot-raw/*.json` — superseded delivery-confounded pilot (cmd-shim transport).
- `probe-unsuitable/repro-0..3.json` — superseded delivery-confounded probes.
- `../delivery-probe-2026-09-20/` — transport A/B verification with NDJSON traces.

## Status

AW-40 live-execution evidence now exists and is auditable. AW-40 completed;
AW-42 reconciliation and AW-20 closure proceed on this evidence.

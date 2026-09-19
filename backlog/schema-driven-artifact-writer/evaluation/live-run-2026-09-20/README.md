# Live paired-model run attempt — 2026-09-20 (endpoint unsuitable; run NOT executed)

## Purpose

AW-40 requires actual fresh manual-arm and Writer-arm model sessions with a
real, fixed model identity. On 2026-09-20 a real local endpoint was located
(`little-coder` CLI → `inclusionai/ling-3.0-flash-fin:free`) and probed with
a preregistered protocol. This directory records that attempt and the
evidence that the endpoint is functionally unsuitable for corpus-scale
structured authoring, so the measured paired run was NOT executed and AW-40
remains open.

## Frozen preregistration

- `spec.json` — frozen parameters (model identity, corpus, arms, budget of 3
  attempts per case/arm, counterbalanced arm order, stopping rule, success
  criterion, uncertainty method) written BEFORE any outcome collection.
- `protocol_amendments` AMEND-1 (system-prompt override; the stock little-coder
  system prompt kept the model agentic/tool-emitting) and AMEND-2 (short user
  prompts; the free-tier endpoint drops requested values from longer messages)
  were recorded before the measured run, as required for pilot-discovered
  protocol defects.

## Raw traces (hash-indexed, see hashes below)

- `pilot-raw/*.json` — pilot runs on CASE-01 (positive task create) and
  CASE-08 (illicit status patch) for both arms, attempt-limit 2, all prompts
  and raw model outputs preserved verbatim.
- `probe-unsuitable/repro-0..3.json` — four additional fresh calls with the
  exact CASE-01 Arm B prompt after AMEND-1/AMEND-2 (reproducibility check).

## Findings

- Pilot: the model never reproduced the requested semantic values for
  corpus-scale payloads; outputs were unrelated ("# Task Create" documentation
  prose, `{"task": {"id": null, ...}}`, `{"project": "DeltaFuse", ...}`
  wrappers, refusals claiming missing specification).
- Reproducibility (4/4 fresh calls, same frozen prompt): outputs
  `{"task": "create"}`, `{"name": "", "description": "", "activeForm": "", "steps": []}`,
  `{"task": "create"}`, `{"task": {"id": null, "title": null, ...}}` — none
  contains a single requested value.
- A 2-field probe (title/kind only) succeeded once, showing the endpoint
  follows trivial payloads but not protocol-scale ones.
- Consequence: neither arm can be executed validly with this endpoint; any
  metrics computed from such outputs would be meaningless. The measured run
  was therefore NOT executed (this is not a waiver: it is recorded as an
  unavailable/unsuitable prerequisite).

## Artifact hashes (SHA256)

- `live_paired_runner.py` `e0e0c5211e9a90674655fe5a1354dbcce29f184b7d1da2096ba4ff24c5f02550`
- `spec.json` `cfd7667e4e1c0d90636c2774cbc062b6a9f19026217b39260ff0c1ca9560eee6`
- `pilot-raw/CASE-01-A1.json` `5d171af9c366c6d7903c0794cae6a8192a0ebf460c0bc3626ce96af8774921e6`
- `pilot-raw/CASE-01-A2.json` `39219da94788c13ea87a8d91598631d97aac289e858c230daec864936ac496e0`
- `pilot-raw/CASE-01-B1.json` `f04333fe8303839f1962550d3d4ea924a368ccbc64c3e90d2ba552f6693a200c`
- `pilot-raw/CASE-01-B2.json` `ae36cfb4174239939f2306e5c9568716e0580ea0b6b8cd8e43be7d1faad53d94`
- `pilot-raw/CASE-08-A1.json` `232f758755667333ee25cdab05157f4012125333475dac8b715dc215935cc179`
- `pilot-raw/CASE-08-A2.json` `d5676037886873201cc63e693102e29dff0b0a68784bd3bfe6a781ef33a875f0`
- `pilot-raw/CASE-08-B1.json` `6e4b46ff6bc6e64d17a22f349505b34dc503a38ac391296564db1d79d946877a`
- `pilot-raw/CASE-08-B2.json` `89829bc386a23ab213aa2937648d29cff4fd94b5a6c1976aa6f68b92eea34cb5`
- `probe-unsuitable/repro-0.json` `187ea2d54f61f9841eef17faede69df0551155382dae5ae840550b4d73dda997`
- `probe-unsuitable/repro-1.json` `904a3a36fc5651cd63c9527e8030203adf54ac2db5a6f4eb9d91c18caf03022e`
- `probe-unsuitable/repro-2.json` `707ecde1e4316d8dfbb442ad162c982160e20afc670d7d179140b7f00496f3c3`
- `probe-unsuitable/repro-3.json` `7d8a2f73a844f160f6564f8fe1864073f02194b3fc4246bae76381b4fa879002`

## Status

AW-40 remains in_progress. Exact prerequisite: an authorized small-model
endpoint that follows structured authoring instructions for protocol-scale
payloads (the probed `inclusionai/ling-3.0-flash-fin:free` via little-coder
does not; `external_model_status` remains unavailable/unsuitable and
`acceptance_status` remains open_for_AW-20). The runner and protocol remain
in place and can be re-run unchanged if a suitable endpoint becomes
available.
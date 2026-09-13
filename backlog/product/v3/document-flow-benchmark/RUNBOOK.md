# Future implementation and qualification runbook

This file is a plan. Commands for scripts.document_flow and new Maven profiles
are proposed interfaces implemented by the named cards; they do not exist yet.
Existing framework command signatures must be rechecked at the qualified SHA.
The current planning task does not execute builds, tests, inference or campaigns.

## 1. Planning versus entry readiness

Planning is complete independently of qualification Wave 3.
Implementation starts at J03-000 after QF-025 is verified and the selected
3.0.0 tree is clean. Capture all hashes again then.

Docker was verified reachable on 2026-09-13: Engine 29.7.2, Linux amd64,
Desktop 4.90.0. Restricted sandbox access denied the named pipe; an authorized
host read succeeded. Do not report that the daemon remains unavailable.
Daemon reachability is not Java 21, cached images, stack or inference readiness.

## 2. Per-card evidence

Set an operator-selected evidence root outside the source tree and Worker mount.
Create fresh card-attempt directories. Save stdout/stderr as bytes plus argv,
cwd role, exact environment/version identity, exit code and content hashes.
Never include credentials. On Windows use the real bundled/local Python,
not a WindowsApps execution alias. Resolve it once per implementation session.

For pure Python cards, the commands in card.test are exact target selectors
once the test exists. On Windows use the verified interpreter path; on POSIX
use its verified counterpart. pytest without the file existing is an expected
initial Red only if the new test has meaningful behavioral assertions.

Expected verification levels:
- Schema/evaluator: deterministic unit, boundary, negative and recomputation.
- Seed/API: Java unit + real PostgreSQL/Kafka integration.
- System/fault: actual pinned Compose services and observed barriers.
- Boundary: real external process/container, effective mounts/network/tools.
- Worker: actual little-coder/Laguna request/response/tool transcript.
Never relabel lower-level evidence as a higher-level result.

## 3. Windows command matrix

From the qualified framework root, with verified interpreter on PATH:

    python -m pytest tests/bench/document_flow/<card-test>.py -q
    python -m pytest tests -q -p no:cacheprovider
    powershell -NoProfile -File tests/smoke-test.ps1
    powershell -NoProfile -File tests/validate-layout.ps1 -ProductDir <installed-public-product>
    python scripts/sync_assets.py --check
    git -c safe.directory=<verified-framework-root> diff --check

Under verified Java 21 and provisioned offline Maven cache:

    mvn --offline -f <public-seed>/pom.xml verify
    mvn --offline -f <public-seed>/pom.xml verify -Pdb-integration
    mvn --offline -f <public-seed>/pom.xml verify -Pmessaging-integration
    docker compose -f <public-seed>/compose.yaml config

J03-208 defines safe build/up/readiness argv and J03-209 runs public smoke.
Capture Docker host OS separately from Linux container OS. Do not treat a Linux
container running under Windows as evidence that Maven also built on Linux.

## 4. POSIX command matrix

Use a separate clean Linux/WSL/POSIX checkout with the same source/input hashes:

    python -m pytest tests -q -p no:cacheprovider
    bash tests/smoke-test.sh
    bash tests/validate-layout.sh <installed-public-product>
    python scripts/sync_assets.py --check
    mvn --offline -f <public-seed>/pom.xml verify
    mvn --offline -f <public-seed>/pom.xml verify -Pdb-integration
    mvn --offline -f <public-seed>/pom.xml verify -Pmessaging-integration
    docker compose -f <public-seed>/compose.yaml config
    git diff --check

Record whether execution was native Linux, WSL or a container. Git Bash smoke
is useful shell compatibility evidence but not a replacement for all Linux
Java/filesystem/isolation checks. Mandatory skips remain blockers.

## 5. Legacy and regression preservation

Use rg against tracked runtime/docs/template/installer paths for:
docs/init, docs/todo, docs/process, deltafuse eval and historical lifecycle
spellings. Classify hits as forbidden runtime use, negative test, migration
guidance or historical quotation. A raw hit count is not the acceptance oracle.
Search excludes run evidence/caches; do not delete historical explanations.

Record M01–M03 and J01 input hashes before and after each integration package.
Run relevant existing tests/unit/test_bench.py, test_bench_m03.py and layout/
installer tests when touching shared benchmark interfaces. If no shared runtime
contract changes, do not gratuitously resynchronize generated assets.
sync_assets.py --check is the required read-only drift probe.

## 6. Provisioning gate

J03-003/201 record exact dependency/image registry sources and immutable hashes.
Provision Maven dependencies/plugins, Python wheels, Node/agent dependencies
and container images separately using approved repositories. Qualification
uses the caches and fixed digests offline. Do not issue a broad Docker prune,
delete unrelated volumes, or permit arbitrary Worker internet to repair cache.

Preflight confirms:
clean qualified framework/judge SHA and frozen pack; Java 21; Maven/plugin
inventory; exact Node/agent dependencies; image digests; supported live file
monitor; available private broker/DB resources; model/tokenizer attestation;
32768 cap/thinking retention; fresh session; effective forbidden-tool and
inference-only egress policy; complete public/private inventory separation.

## 7. Positive/negative/mutation controls

Before any target Worker:
1. Public single-step baseline green.
2. Unchanged seed fails target hidden checks at expected IDs.
3. Private Java reference + full valid process reference passes mandatory checks.
4. All 28 mutant outcomes interpretable; all critical detected; >=90% overall.
5. Frozen contract, budget, reference, generator and judge hashes stored.
6. Source-based replay twice agrees on semantic outputs and score.

Calibrate invocation after J03-605:
    python -m scripts.document_flow calibrate --plan <matrix> --out <fresh-root>

Fault tests use deadline polling and acknowledged barrier triggers; a process
restart by itself is not proof the dangerous transaction interval was reached.

## 8. External pilot and campaign

Before invoking a model, confirm the selected provider/config is the authorized
profile and use its existing configured credentials without persisting secrets.
Missing access is a concrete prerequisite. The plan does not authorize spending
on an unspecified paid model or purchasing credentials/capacity.

The pilot uses actual little-coder with poolside/laguna-xs-2.1 after calibration.
A real Human Gate pauses for an operator choice. No benchmark-author coding
help, extra model, subagents, dispatch or search. Rate limits and infrastructure
failures are recorded; don't silently swap providers or reset run identity.

    python -m scripts.document_flow preflight --plan <pilot-plan> --out <fresh-preflight>
    python -m scripts.document_flow run --plan <pilot-plan> --run-id <id> --out <fresh-run>
    python -m scripts.document_flow replay --run <run-dir> --trusted-manifest <seal>

Then execute all members of the preregistered >=3-run campaign in fresh sessions,
sandboxes and volumes with identical fixed agent/model profile.

    python -m scripts.document_flow campaign --plan <campaign-plan> --runs <root> --out <fresh-summary>

Pilot and campaign have separate IDs. A pilot can become a campaign member
only if it was preregistered as that member before execution and all required
profile/independence rules are met; do not retroactively select a lucky pilot.
Do not replace failed or invalid required runs. An additional diagnostic rerun
has a new identity and never removes the original from the campaign.

Comparison requires same judge/framework/contracts/paired variant schedule.
Use a second real Worker profile only when configured/authorized; otherwise
exercise comparison with clearly labelled synthetic fixtures and do not publish
a fabricated real ranking. A campaign score does not by itself show causality
of framework benefit; see DESIGN section 1.

## 9. Final evidence and readiness verdict

A pilot may validly fail while still providing complete benchmark-operation
evidence. Report benchmark readiness separately from Worker release-pass.
Acceptance requires the reference to pass and the benchmark to distinguish
failures; it does not require a weak Worker to reach 10000.

Read COVERAGE row by row. Verify hashes and command receipts, not just reports
saying pass. Record all mandatory platform limitations, exact first failure
distribution and missing measurements. Leave ready=false if any mandatory
criterion is unproven. Keep scored outputs immutable and source tree clean.

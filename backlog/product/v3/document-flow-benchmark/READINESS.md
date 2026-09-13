> Historical design-readiness observations are preserved below. The user has
> since requested planning only, and the complete handoff is in
> [START-HERE.md](START-HERE.md). See the latest planning update at the end;
> Docker daemon unavailability below is an earlier observation, now superseded.

# J03 readiness observation — 2026-09-13

Status: design prepared; implementation has not begun.

## Confirmed target and source

The user selected the sibling DeltaFuse 3.0.0 repository.
VERSION and pyproject.toml both report 3.0.0.
Observed HEAD: db15ca24cc6af128920165fb7c57d6a18c382978.
Read INSTRUCTION.md in this directory in full before designing.
See [DESIGN.md](DESIGN.md) for the proposed implementation contract.

## Mandatory start condition is not satisfied

INSTRUCTION.md section 2 says:
"дождаться завершения текущей qualification Wave 3" and
"начать с чистого commit и записать его полный SHA".

The checked history ends with QF-022 followed by the benchmark intention
document. qualification-fix-plan-wave-3.md requires QF-025 before Wave 3 is
complete. No QF-023, QF-024 or QF-025 RESULT.md was found in the inspected
qualification-fixes tree. This is a current checkout observation, not proof
that nobody is working on those packages elsewhere.

Pre-existing working changes:

| Path | SHA256 before this design |
|---|---|
| scripts/sync_assets.py | 37bb7b434c228689fcc7649e39f79aac8f8e7630f56e486b7f393eeabf95a9e2 |
| src/deltafuse/assets/__init__.py | 4d4b547752479fd066b8b102d682ba4a512f568cb319b869118d63e968dd1a44 |
| src/deltafuse/assets/manifest.json | 802f4fb4bf05ab6eccf0efd52b3ba3ba74e6bbf0c06d8fc6df1682fbfdf8cc8b |
| tests/unit/test_sync_assets_hash_coverage.py (untracked) | 886bd66bdbc78a3a2c3332e360a5998559b40eac356345402eabaf5f84bd3c15 |

These files overlap the scope of QF-023. Do not stage, commit, revert, or
incorporate them as part of the benchmark. A new clean branch at today's HEAD
would preserve them but would not satisfy the unfinished Wave 3 prerequisite.

## Runtime observations

- PowerShell can locate Maven, Docker CLI, little-coder, uv, and Java.
- Java on PATH is under a JDK 25 installation.
- The inspected Eclipse Adoptium directory contains JDK 17 and JDK 25;
  a usable Java 21 toolchain has not been established.
- docker version --format '{{json .Server}}' failed to connect to the
  docker_engine named pipe. No live Docker stack was executed.
- Docker also reported access denied reading the user's Docker config from
  this sandbox. No credentials were read or modified.
- No model endpoint was invoked; no pilot or campaign has been run.
- No dependency versions/digests have been invented or declared qualified.

## Work performed and remaining

Prepared a concrete design covering package boundaries, independent executable
oracles, per-stage snapshots, score ceilings, provenance precedence, exact
rounding, campaign membership, external Worker isolation, and 24-mutant
calibration. All implementation interfaces in DESIGN.md are proposals.

No framework code, runtime assets, existing cases or qualification evidence
were changed by this design work. Framework smoke/layout tests are not a
qualification result for these planning documents and were not run.

Next: verify QF-025 completion and a clean framework baseline, then implement
package 01 with Red/Green tests. Establish Docker and Java 21 before package 02
acceptance; live external Worker instrumentation is required before pilot
qualification. The overall benchmark is not implemented or qualified.

## End-of-design verification

The four-file preservation comparison detected concurrent change in
scripts/sync_assets.py: its later SHA256 is
c27b72b2129eaad9a7d554683ac10e6ff81abcc0cae046012e2eba7ca82560da.
This task only wrote DESIGN.md and READINESS.md; it did not write that script.
The other three observed file hashes still match the initial values.
Do not claim the whole working tree was unchanged during this session.
HEAD remains db15ca24cc6af128920165fb7c57d6a18c382978.
git diff --check exited 0; it also warned about future CRLF normalization
of the pre-existing modified assets/manifest.json.


## Latest update — comprehensive planning request, 2026-09-13

The user clarified that this task must build a comprehensive implementation
plan for a smaller LLM to execute later. Implementation is not part of this
planning pass. Wave 3 is a future implementation entry gate, not a reason to
leave the planning task incomplete.

Docker was rechecked after the user enabled the daemon. A restricted-sandbox
read got a named-pipe permission denial; the authorized host read succeeded:
Docker Engine 29.7.2, API 1.55, linux/amd64, Docker Desktop 4.90.0.
No image was pulled and no product stack was started.
Installed little-coder package.json reports 1.19.0. This identifies an available
external agent package; it does not establish endpoint/model qualification.

Created a 58-card plan with 85 dependency edges, seven implementation packages
plus prerequisite group, bounded context/write sets, exact Red/Green checks,
scoring/interface decisions, 28-mutant matrix, platform runbook, acceptance
coverage, machine-readable queue, and one-card executor handoff prompt.
All cards remain planned. PLAN-REVIEW.md records structural/arithmetic checks.

Other qualification work changed files concurrently during planning; this
planning task writes only this document-flow-benchmark directory. Re-read git
status and completed qualification evidence in J03-000 instead of assuming
this historical observation is still the current qualification state.

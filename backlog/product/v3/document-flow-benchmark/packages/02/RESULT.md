# Package 02 — result

Status: complete
Package title: Working Java seed — real single-step baseline stack with a
hash-verified, judge-free public pack
Cards: J03-201 through J03-210 (all ten complete; per-card results in
[cards/](cards/) and linked from [README.md](README.md))
Instruction/design/registry revision hashes: intake
`b21881e0f7121b467d1c1337c999c0af75561aa91d395d472778eb1bd591152e`;
public contract decisions
`51cb0d41987e7a8dd524848f1f11732e91cf1561c0924a3312323531b3b4d93a`
(unchanged since the J03-002 freeze).

## Identity

- Full parent implementation SHA: the package starts from
  `0f79e5de9a4daa68bb91477b35992829ec389c10` (J03-201 parent) and ends at
  this result commit's parent; the exact final source SHA is recorded in the
  next evidence-index commit (a commit cannot contain its own hash).
- Clean-tree status: every card committed only its own files; the unrelated
  dirty `process/bench/cases/M03-adversarial/oracle.yaml` was preserved
  unstaged throughout and is not part of any package 02 commit.
- Framework VERSION 3.0.0; dependency lock
  `process/bench/cases/J03-document-flow/dependencies.lock.json` (1009
  artifacts, extended once by the recorded J03-202 scope adjustment).
- Platform/toolchain: Windows 11 amd64, Docker Engine 29.7.2 (linux/amd64
  containers), Eclipse Temurin 21.0.12.1+1, Maven 3.9.12, sealed offline
  cache `j03-provisioning-2026-09-13`. Pinned stack images: PostgreSQL 17.6
  `sha256:00bc8661…`, Apache Kafka (native) `sha256:37edf221…`, Temurin 21
  JRE base `sha256:66bb9006…`, Kafka tools image `sha256:4ceccc57…` (full
  digests in the J03-208/209 results).
- Evidence root: `j03-evidence/J03-202` … `j03-evidence/J03-210` (external,
  hashed per card; no secrets or machine-specific absolute paths in tracked
  files).

## Changes and scope

Exit gate of package 02, as planned: a real single-step baseline stack green
on pinned images, and a public inventory that excludes every private asset.

- J03-201 reactor/toolchain pin and offline inventory (Java 21 enforcer,
  sealed 1009-artifact cache).
- J03-202 baseline DTO/event/API contracts (closed vocabularies, canonical
  JSON, idempotency contract) with public fixtures; no target semantics.
- J03-203 isolated per-service databases, Flyway V1 schemas, principal
  separation, judge read-only grants, migration-contract tests.
- J03-204 document commands; J03-205 single-step workflow; J03-206 Kafka
  inbox/outbox delivery; J03-207 audit projection and canonical flow query
  (completed in J03-209 with real projection clients).
- J03-208 digest-pinned Compose stack, launcher, fault controls, run-owned
  cleanup; J03-209 public end-to-end suite (`J03-PUB-001…012`); J03-210
  realistic noise, target intake with `j03-obligations` witnesses, public
  inventory, and the checked installer.
- Contract decisions/approved scope adjustments (all recorded in the
  corresponding card results): J03-202 JUnit test dependency + lock
  extension (surefire provider); J03-203 root-POM db-integration profile;
  J03-208 `@Autowired` on the two command services, frontend network for
  loopback publishing, launcher state-root/quoting/encoding fixes; J03-209
  real projection clients and endpoint (completing the J03-207 invariant)
  and DEC-D decision-level replay in `WorkflowCommandService`; J03-210
  `judge_pack: pending` staged-case skip in the M03 unit invariant.

## Red, Green and regression

Condensed; exact argv/exit/hashes per card in the linked results.

| Card | Required Red | Green | Regression |
|---|---|---|---|
| J03-201 | FileNotFoundError on absent seed POM; Java 25 enforcer Red | offline `clean verify` on empty reactor | 13-file Python regression green |
| J03-202 | 182 missing-symbol compile errors | 47/47 contract tests | reactor + 179 Python tests |
| J03-203 | missing baseline tables (2 failures/6 errors) | 28 migration tests on live PostgreSQL | default-skip + Python suite |
| J03-204 … J03-207 | per-card results | per-card results (db/messaging profiles) | per-card results |
| J03-208 | tmpfs mount rejection; document-service exit(1); cold cache; wrong digest | 5/5 containers healthy from clean volumes + live smoke | reactor db/messaging + 179 Python tests |
| J03-209 | suite absent; `J03-PUB-005` broken wiring; `J03-PUB-004` stub projections | full public suite on fresh stack; judge-driven live pytest 185 passed | reactor db/messaging green |
| J03-210 | installer/tests absent; 5 installer counterexample failures | installer tests 6 passed; sandbox install + `validate-layout` valid; live suite with noise | reactor green; 190 Python passed, 3 skipped |

Expected Red reasons are specific (named public assertions, SQLStates,
compile symbols, enforcer rules, daemon/manifest errors) — never bare
timeouts. Mocks/simulations: none for the stack evidence; module-scoped
integration tests use Testcontainers. Mandatory checks not executed: POSIX
compose/installer runs and symlink-capable platforms (recorded per card as
later qualification requirements); no Worker pilot, mutation run, campaign,
or Human Gate action belongs to package 02.

## Acceptance and integrity

- Exit gate met: one documented command starts the complete baseline on a
  bounded, offline, digest-pinned, private stack; the public inventory is
  hash-verified and refuses judge material (renamed-oracle counterexample
  included); the target intake publishes the full semantics and witness
  grammar without implementing the target.
- Schema and semantic replay: canonical fixtures round-trip
  byte-identically (J03-202); migrations are checksum-frozen (J03-203); the
  public suite observes real Kafka delivery and watermark convergence
  (J03-209/210).
- No inferred pass from missing events, skips, or absent logs: every card
  binds evidence to full SHAs, exact argv, exits, artifact hashes and
  classification; skipped items are platform skips recorded per card.
- Mutation runs: none belong to package 02 (package 06).

## Handoff

- Completed cards: J03-201 … J03-210 (all).
- Blocked cards: none.
- Next ready card: J03-301 (generate replayable scenario variants; depends
  on J03-210 ✓ and J03-105 ✓).
- Exact next action: execute J03-301 per its card; package 03 owns the
  private oracle pack (`oracle.yaml`, variant contract, interpreter,
  reference) that the staged `judge_pack: pending` marker anticipates.
- Known risks/limitations: Windows-only execution so far (POSIX compose and
  installer runs are later qualification requirements); symlink-positive
  link checks were skipped on this host (reparse detection implemented);
  the `Year.MAX_VALUE` noise defect was caught by the reactor compile and
  fixed within J03-210.

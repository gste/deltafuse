# q6 / tier 1 — output (2026-09-22)

Tier-1 answer to [1-AUDIT.md](1-AUDIT.md), written against framework `0ccd18a`+
(after roadmap item 1: the Worker writes structure only through the Artifact
Writer). Input for [2-DECOMPOSE.md](2-DECOMPOSE.md).

Facts from the repository that shape the answer:

- The catalog schema already carries `status: active | draft | deprecated |
  removed` and per-capability `code_roots`. Neither was enforced until q4 phase 1,
  which now reads `code_roots` to record under-routing (`core/ownership.py`).
- The Bootstrap profile (`project.baseline: draft` → human flips `accepted`) is
  the existing adoption path. It is repository-wide, and after `accepted` the
  leash treats a spec edit outside a Change as an orphan.
- A characterization test is green on the day it is written. DeltaFuse's Declare
  demands Red (`expected-failure`) evidence, so characterization can never enter
  through a Change without a special case. Fuse-Back must therefore work before
  the gate it hands off to, not through it.

---

## 1. DECISION

**Catalog first, characterize by wave, all before `accepted`.** Fuse-Back is a
separate one-shot tool with two outputs.

- **Day one: the skeleton.** Its first run produces the capability catalog for
  the whole repository. Every source file is owned by exactly one capability
  through disjoint `code_roots`, or listed as unowned. All capabilities start
  `status: draft`. It also wires the test runner
  (`workflow.test_commands`) and proves it by running one trivial test.
- **Waves: the characterization.** Each later run characterizes the
  capabilities the adopter names for the first Changes. For each one it writes
  characterization tests pinned green on today's code, and a spec module whose
  requirements are all derived from those passing tests. The capability then
  becomes a candidate for `active`.

The human flips `project.baseline: accepted` when the characterized set covers
the Changes they plan. Capabilities left `draft` are not adoptable. A Change
whose routing names one halts at `analyzed` in box C: "characterize X first".

Fuse-Back refuses to:

- produce a whole-repository spec;
- fix, rename or refactor code;
- write intended behaviour it cannot observe;
- touch anything after `accepted` unless the human flips the baseline back to
  `draft` for a new wave.

## 2. SEQUENCE

| # | adopter does | exists afterwards |
| - | ------------ | ----------------- |
| 1 | `deltafuse init` (baseline `draft`, leash `off`) | `.deltafuse/`, empty `docs/` |
| 2 | `fuse-back runner` — detect or wire the test command, run one smoke test | `workflow.test_commands` in `.deltafuse/config.yaml`; a runner proof in `docs/intake/fuse-back/runner.md` |
| 3 | `fuse-back catalog` — cluster the source tree into capabilities | `docs/spec/_capabilities.yaml`: all `draft`, disjoint `code_roots`, an `unowned` list in the report; `docs/intake/fuse-back/catalog.md` |
| 4 | Human edits and accepts the catalog (plain review, no tool) | the catalog as committed |
| 5 | `fuse-back characterize <capability>...` — one wave | `tests/characterization/<domain>/<capability>/test_*.py` (green on current code); `docs/spec/<domain>/<capability>.md` (requirements `observed`, suspects marked); `docs/intake/fuse-back/<capability>.md` (suspects list) |
| 6 | Human answers each suspect: **law** or **defect** | defects become bug intakes in `docs/intake/`; laws stay as spec |
| 7 | Human sets the characterized capabilities `active` and flips `project.baseline: accepted`, then `workflow.leash: enforce` | Bootstrap closed |
| 8 | First DeltaFuse Change via `/intake` | normal lifecycle; every Verify now runs the characterization suite |

Steps 5–6 repeat per wave. A wave after step 7 needs the baseline flipped back
to `draft` for its duration. That is a human decision recorded in git history.

## 3. CHARACTERIZATION

- **Observation, then pinning.** For one capability, a dense model reads that
  capability's `code_roots` and proposes calls with inputs across public entry
  points. Fuse-Back runs every proposed test on current code and keeps only the
  green ones. The assertions are the observed outputs, filled in by running the
  code, not predicted by the model. The model never writes an expected value:
  the process runs the call and records the result. This makes the bulk work
  safe for a weak model.
- **Spec from tests.** Each kept test becomes one requirement,
  `REQ-<CAP>-NN (observed)`, phrased in EARS. It carries a back-reference to
  its test. The spec says what is, not what should be.
- **Suspected defects: flag, encode anyway, ask once.** A deterministic list of
  suspicion rules marks a behaviour `suspect`:
  - an exception swallowed or turned into `None`;
  - an output contradicting the function's name or docstring;
  - two entry points disagreeing on the same input;
  - non-determinism across two runs.

  A suspect is still pinned, so change detection is total. Its test carries
  `@pytest.mark.characterization_suspect`, and its requirement is marked
  `suspect` in the spec. At step 6 the human decides each one.
  - **Law:** the marker is removed.
  - **Defect:** the requirement is removed, and a bug intake is written that
    names the test. The bugfix Change then modifies that test through DeltaFuse
    like any other.

  The first real Change therefore contradicts only behaviour a human already
  called a defect.

## 4. HANDOFF

**Files.** DeltaFuse receives only artifacts it already knows:

- `docs/spec/_capabilities.yaml` (`process/schemas/capability.schema.yaml`);
- `docs/spec/<domain>/<capability>.md` (spec modules; prose with requirement
  anchors);
- `tests/characterization/**` (ordinary tests);
- `workflow.test_commands` in `.deltafuse/config.yaml` (the config schema);
- `docs/intake/fuse-back/*.md` (prose intakes).

There is no new schema and no new artifact kind.

**Verification at handoff** (step 7). All of it uses existing commands plus
one catalog rule:

1. `deltafuse validate-config .` and `deltafuse validate-layout .` pass.
2. Every `workflow.test_commands` entry passes on the current tree. This proves
   the characterization is green where Fuse-Back left it.
3. **New catalog rule in DeltaFuse:** `code_roots` of `active` capabilities are
   disjoint. q4 needs this for its detector's resolution, and it applies to any
   catalog, so it is not Fuse-Back-specific. `draft` capabilities are exempt,
   so the rule does not block a partial adoption.

**Incomplete output.**

- A capability without characterization stays `draft`, and routing to it halts
  (box C, the message names the capability).
- A failing characterization test at handoff means Fuse-Back pinned something
  flaky: handoff fails at check 2 and the test is removed or fixed in the next
  wave.
- An `unowned` source path is recorded. q4's ownership record reports it per
  Change; no gate.

## 5. BOUNDARY

DeltaFuse learns nothing about Fuse-Back. It gains two rules that stand on their
own:

- **(a) disjoint `code_roots` for `active` capabilities.** This is justified by
  q4 (a detector with overlapping roots is blind; bench case M02 has resolution
  1.0).
- **(b) routing to a `draft` capability halts at `analyzed` (box C).** This is
  justified by the catalog's own `status` field: a capability without accepted
  spec cannot be specified against. Bootstrap under `baseline: draft` stays
  exempt.

Both rules would be right without Fuse-Back existing.

## 6. MODEL TIERS

| part | tier | volume (repository of ~500 source files, ~40 capabilities) |
| ---- | ---- | ------------------------------------------------------------ |
| runner wiring | none (detection rules) + human | once |
| catalog clustering | frontier, or dense ≤40B with human edit | one pass over the directory tree and module docstrings, ~50–150k tokens |
| characterization calls | **dense ≤40B** | per capability ~20–60 calls proposed, each checked by execution; ~40 capabilities × ~10–30k tokens |
| spec from kept tests | **dense ≤40B** | one requirement per kept test; mechanical |
| suspicion rules | deterministic; optional dense pass for docstring contradiction | per suspect, small |

The only frontier-worthy step is clustering, and a human edits its output anyway
(step 4).

## 7. FALSIFIERS

Measured on at least two real repositories (≥200 source files, <30% line
coverage). Neither is a bench case: this needs a corpus in `deltafuse-bench`
with repositories under a licence that allows it.

1. **Skeleton quality.** The share of `code_roots` the human reassigns at
   step 4. If it is **> 30%**, clustering the whole tree up front wastes more
   than it saves, and the runner-up wins: catalog entries discovered per
   Change.
2. **Characterization yield on dense ≤40B.** The share of proposed calls that
   run and are kept. If it is **< 50%**, the bulk step needs a frontier model;
   price it into the adopter's cost and revisit MODEL TIERS.
3. **Net strength.** Mutation score of the characterization suite on its
   capability (mutants limited to `code_roots`). If it is **< 50%**, the suite
   does not protect adjacent code, and the headline claim stays unverifiable.
   Then add property-style calls, not more example calls.
4. **Suspect precision.** The share of `suspect` flags the human calls
   **defect**. If it is **< 30%**, the rules cost more attention than they
   save: drop flagging and encode everything silently.
5. **Time to first Change.** Adopter hours from step 1 to the first
   `converged` Change on one characterized capability. If it is **> 8 hours**,
   the wave model is too heavy for adoption.

## 8. UNKNOWNS

- **Flipping the baseline back to `draft` for a later wave.** The leash and the
  queue accept the switch, but whether teams will accept a repository-wide mode
  switch for one capability is untested. The assumption is yes, since it is a
  git-recorded human act.
- **Languages.** Pinning by execution is language-agnostic, but the call
  harness is not. The assumption is Python first. J03 (Java services) is the
  first non-Python target and would need a JVM harness.
- **Non-deterministic code** (time, randomness, I/O). The assumption is that
  the suspicion rule "differs across two runs" catches it and the human makes
  it deterministic by injection. That is a code change and happens through a
  DeltaFuse Change after adoption, so such behaviour is left unpinned
  meanwhile.
- **Test runners with global state or slow suites.** The assumption is that
  characterization tests are fast and isolated by construction (one call each).
  This is unverified on real repositories.
- **Rule (b) "routing to a draft capability halts".** It is not implemented. It
  is a small `check_gate` addition, but it changes behaviour for existing
  catalogs that mark capabilities `draft` casually. The assumption is that none
  do in practice. Tier 2 must add it behind the `baseline: accepted` condition
  only.

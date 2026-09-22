# q6 / tier 1 — AUDIT & DECIDE (high-end model)

Run in a fresh chat with access to the DeltaFuse repository. This message is the
whole prompt.

---

## Your role

You are scoping a **new, separate tool** — working name Fuse-Back — that makes an
existing untested monolith adoptable by a spec-driven framework. You produce
**one scope decision** plus the evidence that would overturn it. You do not write
code and you do not redesign DeltaFuse.

## Context

DeltaFuse drives an LLM Worker through Intake → Analyze → Specify → Decompose →
Declare → Implement → Verify against a product repository where `docs/spec/**` is
the **sole implementation law**. A deterministic Core (Python, no LLM calls,
dependencies `jsonschema` and `pyyaml`) sequences steps, bounds reads and writes,
and checks gates. Target Worker class: dense model up to 40B
(reference `qwen/qwen3.8-27b`), 128k context, 64,000 tokens / 24 unique files
per call.

Product repository shape DeltaFuse expects:

```
product/
├── .deltafuse/{config.yaml,lock.yaml}
└── docs/{intake,changes/<id>/tasks,spec,decisions,archive}
```

Capabilities are the unit of routing: a repository-specific, human-gated
capability catalog `docs/spec/_capabilities.yaml` (schema
`process/schemas/capability.schema.yaml`) maps each capability to spec
references (`catalog_spec_refs(product_root, capability)`) and declares
`code_roots`, `test_roots`, `type` and a `status` of `active | draft |
deprecated | removed`. The test runner is declared in `.deltafuse/config.yaml`
as `workflow.test_commands` (a runner allowlist); evidence is produced only by
running those commands.

**An adoption path already exists — know it before you add one.** The Bootstrap
profile (`docs/workflow.md`): `project.baseline: draft` → draft the catalog →
resolve foundational Decisions (`change: null`) → author the baseline spec
through Analyze and Specify → a human flips `project.baseline: accepted`; after
that `docs/spec/**` changes only through Changes and the leash treats a stray
spec edit as an orphan. Bootstrap assumes a human or Worker writes the spec from
intent; it has no step that reads existing code and no characterization tests.
Your design must say whether Fuse-Back feeds Bootstrap (produces what the
`draft` phase needs), replaces it for brownfield repositories, or sits beside
it — and why.

**A constraint from q4 (analyze routing).** The planned under-routing detector
maps the Implement diff to capabilities through `code_roots`. When capabilities
share a root it is blind (the M02 bench case: three capabilities, one
`src/ratelimit`). A catalog Fuse-Back extracts from a monolith is exactly where
overlapping roots will appear. Say whether the handoff requires disjoint
`code_roots`, and what happens to code no capability owns.

## The problem

Nobody has a greenfield repository with a complete specification. Every real
adopter has a monolith with no spec and often no tests. If DeltaFuse cannot be
adopted into existing code, its addressable set is roughly empty.

Adoption requires a reverse pass: **code as source of truth, spec as result** —
the inverse of the framework's central invariant.

## What is already decided — do not re-open

1. **The FSM stays unidirectional. `docs/spec/**` remains the sole law.**
2. **Fuse-Back is a separate one-shot tool that produces artifacts and hands off.
   It does not enter the DeltaFuse FSM at any point.**
3. **Rejected: "code as intake behind a flag, substituting for
   red/implement/verify."** A flag that skips three of seven stages is a second
   direction of truth wearing different clothes — every downstream gate would
   have to know the flag's state. That is the mechanism by which the `gate`
   concept already spread across 18 of 38 Core modules. It does not preserve
   unidirectionality; it breaks it more quietly.
4. **The capability catalog is the handoff artifact.** It is the only artifact
   that describes the code rather than a change, so Fuse-Back's output (populated
   catalog + spec refs) coincides with DeltaFuse's precondition exactly.
5. **DeltaFuse does not require pre-existing tests to run.** Declare writes a new
   test for new behaviour and proves it red; that works at zero coverage. What is
   required is a wired-up test runner, not a suite.
6. **The real reason tests matter is different and larger.** Without
   characterization tests you cannot detect regression in the **untouched** parts
   of a monolith. The leash bounds intentional writes by path; it says nothing
   about behaviour. So the framework's headline claim — "almost no degradation of
   adjacent code" — is **unverifiable** in an uncovered repository: it rests on a
   diff boundary with no behavioural net underneath.
7. **Therefore Fuse-Back's deliverable is spec + characterization tests, and the
   tests are the more valuable half.** They are what makes every subsequent
   Verify mean anything.

## Your decision

**What is the minimum output of Fuse-Back that makes a monolith adoptable, and
what is the handoff contract?**

Three sub-questions, all of which your decision must answer:

### (a) Scope — how much is extracted, and in what order?

A monolith's full specification is enormous and extracting it up front is a
project, not a step. Options include: extract everything before adoption;
extract per capability on demand, driven by the first Changes; extract a
skeleton catalog first and fill spec lazily. Choose, and say what the adopter
does on day one.

### (b) The characterization-test tension

Characterization tests encode **current** behaviour, including bugs. That is the
point — you want change detection — but it means a Fuse-Back suite promotes
existing defects to specification. State how the tool handles this: does it
distinguish intended behaviour from observed behaviour, does it flag suspected
defects for a human gate, or does it deliberately encode everything and accept
that the first real Change will contradict some of it?

### (c) The handoff contract

What exactly does DeltaFuse receive, how does it verify that what it received is
usable, and what happens when Fuse-Back's output is incomplete? Name the files,
the schemas they must satisfy (existing schemas live in `process/schemas/`), and
the check that runs at handoff.

## Constraints you must respect

- Fuse-Back shares nothing with DeltaFuse's FSM. If your design needs DeltaFuse
  to know Fuse-Back exists beyond validating its output artifacts, say so
  explicitly and justify it — that is a boundary violation and needs defending.
- Characterization-test generation is **high-volume, low-judgment work**, unlike
  analysis. It is a plausible weak-model workload. If your design requires a
  frontier model for the bulk of the work, say why and what that costs the
  adopter.
- The adopter's repository may have no test runner wired at all. Say where that
  falls in your sequence.
- Reuse existing schemas and vocabulary where they fit. Inventing a parallel
  artifact vocabulary is a cost — price it. Writes to DeltaFuse artifacts go
  through the Artifact Writer (`deltafuse artifact create|update`, receipts in
  `.deltafuse/receipts/`); roadmap item 1 is moving every Worker write there, so
  a handoff that hand-writes YAML is already behind the framework.
- The bench judge lives in a separate repository, `deltafuse-bench`. A
  falsifier measured "on a real repository" needs a corpus there; name what it
  must contain.

## What would end this question

State explicitly, as a numbered list, **what observation would settle your scope
choice against the runner-up.** Each item must be measurable against a real
repository — "run Fuse-Back on a monolith of N files and measure X, where X > Y
flips the decision". Arguments are not falsifiers.

## Output contract

Produce exactly these sections, in this order. No preamble.

1. **DECISION** — the scope, in one paragraph. What Fuse-Back produces and what
   it refuses to produce.
2. **SEQUENCE** — what the adopter does, in order, from an untested monolith to a
   first DeltaFuse Change. Name the artifact that exists after each step.
3. **CHARACTERIZATION** — your answer to (b), concretely: how observed behaviour
   becomes tests, and how suspected defects are handled.
4. **HANDOFF** — your answer to (c): files, schemas, the verification that runs,
   and the failure mode when output is incomplete.
5. **BOUNDARY** — everything DeltaFuse must know about Fuse-Back. Ideally this is
   "the output artifacts and nothing else"; if it is more, defend it.
6. **MODEL TIERS** — which parts of the sequence need a frontier model and which
   run on a dense <=40B model. Give rough volumes.
7. **FALSIFIERS** — the numbered list from above.
8. **UNKNOWNS** — what you could not determine, and what you assumed. "More
   research needed" is not an entry.

Do not produce an implementation plan. That is tier 2.

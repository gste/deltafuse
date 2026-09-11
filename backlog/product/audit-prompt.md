# DeltaFuse framework audit — full review brief

Промпт для внешнего аудита (AU-001). Скармливать моделям целиком или резать по секциям **A–H**. Репозиторий: `gste/deltafuse`, локальный checkout `vendor/deltafuse` / `…/deltafuse`.

---

You are auditing **DeltaFuse** (repo: `gste/deltafuse`, package/CLI token `deltafuse`, current line ~2.5.x).
This is the **canonical framework repository**, not a product app.
Your job: find defects, weak spots, incoherence, adoption friction, missing tests, and credible development bets — including what to steal from peer frameworks — without inventing product features for imaginary apps.

Work **read-only**. Do not edit files, do not invent APIs that are not in the tree, do not propose renaming Core/Worker/Process vocabulary unless you have a strong evidence-based reason and mark it as a breaking proposal.

---

## Locked vocabulary (do not redefine)

- **Process** = lifecycle only:
  `Intake → Analyze → Specify → Decompose → Declare → Implement → Verify`
- **Red / Green** = evidence states inside Declare / Implement, **not** lifecycle step names.
- **Core** = machine that enforces Process (`deltafuse next`, `evidence`, `check-gate`, `decide`, `leash`, `archive`, `board`). Core does **not** write product prose or product code.
- **Worker** = LLM or human who writes the same Change artifacts. Skills bind an LLM; `deltafuse next --human` binds a person. Worker ≠ CI job ≠ Human Gate.
- **Human Gate** = Process stop (Decision / spec accept / merge). Never auto-accept.
- **Pin vs checkout**:
  - Product pin: `.deltafuse/config.yaml` + `.deltafuse/lock.yaml` (product git)
  - Nested framework checkout: recommended `vendor/deltafuse` (submodule/vendor)
  - Do **not** put the submodule inside `.deltafuse/`
- Canonical process docs live only in the framework `docs/**`. Installer must **not** copy them into products.
- Through-mode: `/run` follows `deltafuse next` until Human Gate, failed gate, or empty queue.
- Sibling host UI (**fuse-map**) and Cursor plugin are **outside** this repo’s Core pin. Do not demand they be vendored into `src/deltafuse/**` unless you argue a clear boundary change.

---

## What DeltaFuse claims to optimize for

Use this as the product thesis when judging fit:

- `docs/spec/**` is implementation law.
- Changes are provenance + typed deltas, not chat plans.
- Context is sliced (capability + artifact layer), not whole-repo dumps.
- Gates are machine-checked; evidence is stamped by Core (`deltafuse evidence`), not hand-written YAML.
- Write surface is constrained (`envelope` / `deltafuse leash`); hosts SHOULD cut write-tools to `envelope.write`.
- Human Gates are real stops (`deltafuse decide` journals clicks).
- Benchmarking is agent-agnostic disk scoring (`deltafuse bench`), no LLM-in-the-loop judge.

If something in the repo fights this thesis, call it out.

---

## Required reading order (skim → deep)

**Must read before conclusions:**

1. `AGENTS.md`, `README.md`, `CHANGELOG.md` (esp. 2.3–2.5 + Unreleased)
2. `docs/README.md`, `docs/workflow.md`, `docs/state-machine.md`
3. `docs/core-and-worker.md`, `docs/roles.md`, `docs/context-model.md`
4. `docs/using.md`, `docs/contracts/halt.md`, `docs/contracts/leash.md`, `docs/contracts/board-snapshot.md`
5. `docs/bench.md`, `docs/testing-strategy.md`
6. `process/skills/**` (all lifecycle skills + `/run`)
7. `process/schemas/**`, `process/templates/**` (esp. `.deltafuse/config.yaml`, change templates, CI leash workflow)
8. `src/deltafuse/**` (CLI surface + core enforcement: queue/next, gates, evidence stamp, leash, decide journal, installer/adapters)
9. `tests/**` (unit + integration; note what is *not* covered)
10. `backlog/**` (living intent vs shipped 2.5 iron leash)
11. `process/bench/cases/**` (what the bench actually measures)

Also search for legacy tokens / drift: `delta-fuse`, `docs/todo`, `docs/init`, `docs/process`, `provenance`, old step names, dead CLI, TODOs, `# noqa`, skipped tests.

Russian docs (`*.ru.md`) exist — check EN/RU drift on any finding that touches docs.

---

## Non-goals

- Do not redesign DeltaFuse into a generic chat agent framework.
- Do not propose removing Human Gates “for speed”.
- Do not propose merging pin (`.deltafuse`) and checkout into one git tree without a migration plan and threat model.
- Do not treat fuse-map / Cursor buttons as Core deliverables unless you explicitly argue the boundary should change.
- Do not grade “more YAML” as automatically bad; grade **YAML tax vs enforcement value**.
- Do not recommend `git push` automation or auto-merge.

---

## Peer frameworks / systems to compare (steal carefully)

Compare DeltaFuse to at least **6** of these (more is better). For each: what they do better, what DeltaFuse already does better, and **one portable idea** with adaptation cost (S/M/L) and risk to Core/Worker split.

Suggested set:

1. **OpenSpec** — lightweight spec-driven agent kits
2. **GitHub Spec Kit / spec-kit** — specify → plan → tasks flow
3. **BMAD-METHOD** (or similar multi-agent role packs)
4. **Aider** — repo map, conventions, tight edit loops
5. **Continue.dev** / **Cursor Rules+Skills** — host-native agent contracts
6. **Claude Code / Codex skill packs** — executable skills, hooks
7. **OpenAI Swarm / Autogen / CrewAI** — multi-agent orchestration (only for process ideas; don’t copy chatty orchestration into Core)
8. **dbt / Terraform / Kubernetes admission** — policy-as-code + gated apply metaphors for leash/gates
9. **TLA+ / Alloy / Pact / contract testing** — oracle and convergence ideas
10. **Semantic Kernel / LangGraph checkpointing** — durable run state vs `change.yaml` + journals
11. **Conventional Commits / Changesets / ADRs** — Decision & archive UX
12. **pytest + hypothesis + mutation testing** — evidence authenticity beyond exit codes

If you know a better peer, include it — but stay concrete.

---

## Audit dimensions (cover all)

### A. Conceptual coherence
- Is Core / Worker / Process / Human Gate consistently enforced in docs, skills, and code?
- Where can a Worker still fake progress (hand-edit gates, skip `next`, write outside envelope, stamp-less evidence)?
- Bootstrap (`project.baseline`) vs steady-state Changes — gaps, footguns.
- Through-mode `/run` vs single-step skills — deadlock, loop, or prompt bloat risks.

### B. Lifecycle & state machine
- Gate ordering, partial Analyze (routing/slice/coverage), Specify one-slice, Declare Red authenticity.
- Routes (`code` / `docs` / `ops`) — completeness, orphan paths, archive rules.
- Decision convergence — too heavy / too weak / unclear UX for halt choices.

### C. Contracts & schemas
- Schema/skill/template/docs/tests drift.
- First-write YAML tax: synonym hints help or still hostile?
- Halt + leash contracts: host-enforceable? missing fields? versioning?
- Board snapshot: enough for fuse-map? over-coupled?

### D. Core CLI & enforcement quality
- `next` selection correctness and explainability.
- `check-gate` error quality (actionable vs opaque).
- `evidence` authenticity (private-symbol tests, import failures, `_` red tests).
- `decide` journal integrity / replay / tamper story.
- `leash` modes (`off` / `advisory` / `enforce`): defaults, pet vs production, CI hook gaps.
- Installer/adapters (`link`/`copy`/`auto`), Windows junctions, lock hash story.
- Failure modes when framework is missing from CI (`vendor/deltafuse`).

### E. DX / adoption
- Time-to-first-useful-Change for a new product repo.
- Cognitive load for humans using `--human`.
- Docs discoverability; EN/RU parity.
- Who-is-this-for positioning vs OpenSpec/Spec Kit — honest? missing migration guide?
- Upgrade story (`init --force`), active Change version skew.

### F. Evaluation & quality system
- Bench case coverage (floor vs frontier): what skill/failure modes are unmeasured?
- Score formula (`0.6 correctness + 0.4 process`) — gaming risks?
- Pack isolation (worker must not see oracle) — holes?
- Framework’s own test pyramid vs claimed `docs/testing-strategy.md`.
- Missing mutation / property / adversarial Worker tests.

### G. Security / integrity / supply chain
- Skill snapshot trust, lock pins, submodule URL assumptions (`gste/deltafuse`).
- Prompt injection via intake → Worker write paths.
- Leash bypass if host cannot cut tools.
- Secrets in templates/hooks; dangerous defaults.

### H. Roadmap / competitive bets
Propose a ranked roadmap (P0/P1/P2) for the next 1–2 minor versions:
- keep / strengthen iron leash
- reduce YAML tax without weakening gates
- host integrations (without owning UI in Core)
- bench expansion
- optional profiles (narrow pets vs regulated products)
Each bet: problem → proposal → why now → cost → risk to invariants → success metric.

---

## Method

1. Map the architecture in ≤15 bullets (components + trust boundaries).
2. Produce findings with evidence (path + symbol/section). No vibes-only claims.
3. Separate **bugs/invariants broken** from **product opinions**.
4. Call out **unknowns** explicitly (what you could not verify without running tests).
5. Prefer fewer sharp findings over long soft essays.
6. When recommending borrows from other frameworks, name the mechanism and the adaptation into Core vs Worker vs host.

If you can run tests, do: `pytest` / smoke scripts noted in `AGENTS.md`. If not, say so and reason from code.

---

## Output contract (strict)

Respond in this structure:

### 0. Executive verdict
5–8 sentences: what DeltaFuse is unusually good at; the top 3 risks to its thesis; whether it should double-down or simplify.

### 1. Architecture map
Bullets + one ascii or mermaid diagram of Core vs Worker vs product vs host.

### 2. Findings table
Columns:
`ID | Severity (P0–P3) | Area (A–H) | Finding | Evidence (paths) | Impact | Suggested fix | Effort (S/M/L) | Invariant risk`

Severity:
- **P0** breaks stated invariant or enables silent Process skip
- **P1** high adoption / correctness friction
- **P2** maintainability / docs / test gap
- **P3** polish / optional bet

### 3. Incoherence / drift list
EN↔RU, docs↔skills↔schemas↔code, legacy names, dead ends.

### 4. Peer steal-sheet
Table: `Peer | Strength | Portable idea | Where it lands (Core/Worker/host/docs) | Cost | Risk`

### 5. Bench & test gaps
What failures a cheating/confused Worker can still score well on; what CI does not catch.

### 6. Roadmap (90 days)
Ordered P0→P2 work packages with acceptance checks.

### 7. Anti-roadmap
Things **not** to do (with one-line why).

### 8. Open questions for the maintainer
Max 10 sharp questions (decision-shaped, not research essays).

### 9. Confidence
High/Med/Low per major section + what would change your mind.

---

## Calibration notes for the auditor

- Favor **mechanical enforceability** over aspirational prose.
- A smaller Process that the Core can actually police beats a richer Process the Worker can roleplay past.
- “Make skills longer” is usually the wrong fix; prefer Core checks, better errors, better envelopes, better benches.
- Preserve: no auto-accept Decisions/spec/merge; no product requirements in framework repo; pin ≠ checkout.

Begin the audit now.

---

## Parallel split (optional)

| Lane | Sections | Focus |
|---|---|---|
| A | preamble + A–B | concept + FSM |
| B | preamble + C–D | contracts + Core CLI |
| C | preamble + E–F | DX + bench |
| D | preamble + G–H + peers | security + roadmap |
| Merger | all lane reports | one Output contract; dedupe by Evidence path; on conflict keep stricter Severity and mark dissent |

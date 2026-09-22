# q4 / tier 1 — AUDIT & DECIDE (high-end model)

Run in a fresh chat with repository access. This message is the whole prompt.

---

## Your role

You are auditing one specific architectural gap in a spec-driven development
framework. You are not reviewing the codebase generally, and you are not writing
code. You produce **one decision** plus the evidence that would overturn it.

## The framework in one paragraph

DeltaFuse drives an LLM Worker through a fixed lifecycle — Intake → Analyze →
Specify → Decompose → Declare → Implement → Verify — against a product repository
where `docs/spec/**` is the sole implementation law. A deterministic Core (Python,
no LLM calls, two dependencies: `jsonschema` and `pyyaml`) sequences the steps,
bounds what the Worker may read and write, and checks gates. The Worker is bound
by one `SKILL.md` per step. Target Worker class is a **dense model of up to 40B**
(reference: `qwen/qwen3.8-27b` via OpenRouter) with a 128k context window.
Qualification thresholds live in the separate judge repository
`deltafuse-bench/qualify/thresholds.md`: a full call must fit 131,072 tokens
(T4, gating), framework-controlled input is budgeted at 64,000 tokens
(`DEFAULT_TASK_BUDGET` in `core/context.py`; T4b, observed and penalised) and
**24 unique files per call** (T5, gating). Gate retries (T3) are capped at 2 per
run and 1 per stage.

## The gap

`src/deltafuse/core/analyze.py` runs three passes: `routing | slice | coverage`.
Core sequences them and bounds reads via `analyze_allowed_read(pass_name,
spec_refs)`. That part works.

But `routing.yaml` is **written by the model**. `routing_primary_capabilities()`
only reads back what the model asserted. `uncovered_primary_capabilities()`
checks coverage against what routing already claimed.

**Therefore: if routing under-claims an affected spec domain, nothing in the
framework detects it.** Everything downstream is consistently wrong — slices,
coverage, tasks, red, green, verify all pass, because each is checked relative to
routing. The delta was simply never scoped to include the missed domain.

This is the only lifecycle stage without an independent deterministic falsifier.
Every other gate checks its result independently; routing checks itself.

Consistent with `analyze` being the heaviest skill (786 words, ~1,550 tokens by
the Core's bytes/3.75 estimate, against a 64k budget) on the stage the
maintainer names as weakest.

## What the baseline shows (2026-09-22)

The q0 baseline is one run per case on `qwen/qwen3.8-27b`: M01 (`cooldown`,
converged, correctness 100), M03 (`adversarial`, converged, correctness 100),
M02 (`policy-stats`, partial). The run sandboxes were checked by hand against
the settled detector design below:

- **Observed under-routing: 0 of 3.** Every capability whose `code_roots` the
  diff entered was claimed in `routing.yaml`.
- **The corpus cannot show under-routing.** M01 and M03 have a single
  capability in `docs/spec/_capabilities.yaml`, so routing cannot miss one. M02
  has three capabilities (`security.ratelimit`, `security.rate_policy`,
  `monitoring.usage_stats`) that all declare the same `code_roots:
  [src/ratelimit]`: any touched file maps to all three, so a path-based
  detector cannot tell which domain the code entered.
- **Analyze retries are format, not scope.** M03 needed 13 analyze retries; the
  loop was the `routing.yaml` schema (field shapes), not a missed domain. T3 on
  analyze is today dominated by the structural-format defect class (T10, roadmap
  item 1), which the under-routing work must not be credited or blamed for.

So "under-routing is the dominant failure mode" is neither confirmed nor
refuted: the instrument and the corpus are both missing.

## What is already decided — do not re-open

1. **Core stays strictly deterministic.** No LLM calls in Core. This invariant
   currently holds and is not up for negotiation.
2. **Detector before prevention.** You cannot fix what you cannot observe, and
   you cannot evaluate a remedy without a metric. The detector ships first.
3. **The detector design is settled:** after Implement, compute from the git diff
   which spec domains the code actually touched, and compare against
   `routing.yaml`. Code entered a domain routing did not claim → routing was
   incomplete. Fully deterministic, built on existing machinery
   (`leash.git_dirty_paths`, `catalog_spec_refs` maps capability → spec refs).
   It emits a new scored defect class: **under-routing rate** — the judge
   already reserves slot **T9** for it (observed, not gating; the runner reports
   `under_routing_rate: null` until the detector exists).
   Open inside this design, and yours to answer: the mapping is only as sharp as
   the catalog's `code_roots`. When capabilities share a root (M02 above), the
   detector must either refuse to score (and say so), fall back to a finer
   signal, or require disjoint roots at catalog validation. Pick one.
4. **Lexical methods are tried before embeddings.** BM25 / TF-IDF / term overlap
   against capability vocabularies are fully deterministic, need no weights, no
   runtime, no pinning. Spec domains are named with the words people use to write
   about them; embeddings win on paraphrase, and domain routing rarely
   paraphrases.
5. **If an embedder enters at all, it emits a signal recorded in the receipt, not
   a gate verdict.** A cosine of 0.6199 vs 0.6201 against a 0.62 cutoff flips a
   binary decision from fourth-decimal drift (runtime version, BLAS, batch size,
   hardware). Gates stay deterministic; the embedder lives in observability.

## Your decision

**Given the detector is built and reporting an under-routing rate, what prevents
under-routing — and does an embedder enter Core at all?**

Choose one and defend it:

- **A.** Lexical only. A deterministic index (BM25 or equivalent) over spec
  domains gives Core a candidate set; Core raises a gate when routing omits a
  high-ranked domain. No new dependency.
- **B.** Lexical gate plus an optional embedder as a receipt-recorded signal,
  shipped as `deltafuse[semantic]`, degrading correctly when absent, with the
  presence/absence recorded per run.
- **C.** No preventive mechanism. The detector alone is sufficient: under-routing
  becomes a scored defect, and the fix is a better `analyze` skill or a split
  `analyze` pass, not a Core mechanism.
- **D.** Something you argue for that is not A, B or C.

Note on C: the maintainer's suspicion is that under-routing will be the
**dominant failure mode** on a dense <=40B model. If that is right, C leaves
the dominant failure unaddressed. If it is wrong, A and B add Core surface for a rare defect.
You do not have this number yet — say what it would have to be for each option to
win.

## Constraints you must respect

- Two dependencies today (`jsonschema`, `pyyaml`). An embedder means 100MB–1GB of
  weights, a runtime, and a model pinned by hash. The framework installs into
  corporate and air-gapped repositories. Price this explicitly.
- Hash-pinning machinery exists (`core/assets.py` with `verify_manifest`,
  `.deltafuse/lock.yaml`) — reuse it rather than inventing a second mechanism.
- The optional-dependency pattern already bit once and was fixed: the token
  counter (`core/context.py`, `count_tokens`) used to change results silently
  when `DELTAFUSE_TOKENIZE_URL` was absent. Since Q0-2 every count carries its
  mode (`endpoint` or `heuristic`, with the heuristic id `a04-01`) into the
  receipt, and `DELTAFUSE_TOKENIZER_REQUIRED` turns a missing endpoint into a
  refusal during qualification. Anything optional you propose must follow the
  same rule — the mode is recorded, and a campaign can forbid the fallback. Say
  how.
- Every added gate is a place a weak model can fail. More gates → more retries →
  worse T3 (`gate_retries_total` ≤ 2 per run). Analyze already spends most of
  the budget on format retries (see the baseline). Justify any new gate against
  that cost.
- `analyze` is already the heaviest skill. If your proposal adds instruction load
  to the Worker, say how much and against the 64k budget.

## What would end this question

State explicitly, as a numbered list: **what observation would settle the choice
between your option and the runner-up.** Each item must be something measurable
from a qualification run, not an argument. If your answer is "run the detector
for N changes and look at the under-routing rate", give N and give the threshold
that flips the decision — and say which bench cases can produce it: the current
three cannot (see the baseline), so name the property a new case must have
(e.g. at least two capabilities with disjoint `code_roots`, a request that
reaches the second one only implicitly).

## Output contract

Produce exactly these sections, in this order. No preamble, no summary of these
instructions.

1. **DECISION** — one of A/B/C/D, one paragraph, no hedging.
2. **MECHANISM** — how it works, concretely, naming the modules it touches and
   the artifacts it reads and writes.
3. **COST** — dependencies added, Core surface added, Worker instruction tokens
   added, new gates added and which of the three buckets they fall into (Core
   fixes / model fixes on retry / human halts).
4. **REJECTED** — the runner-up and the specific reason it lost. One paragraph.
5. **FALSIFIERS** — the numbered list from "What would end this question".
6. **UNKNOWNS** — what you could not determine from the repository, and what you
   assumed instead. Be specific; "more research needed" is not an entry.

Do not produce an implementation plan. That is tier 2.

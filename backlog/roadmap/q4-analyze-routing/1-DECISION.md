# q4 / tier 1 — output (2026-09-22)

Tier-1 answer to [1-AUDIT.md](1-AUDIT.md), produced against framework
`3a26a0a` and bench `a2b835f`. Input for [2-DECOMPOSE.md](2-DECOMPOSE.md).

Facts found in the code while auditing, which the prompt did not state:

- **The catalog's per-capability `code_roots` are not enforced anywhere.**
  `grep code_roots src/deltafuse/core` finds only `workflow.code_roots` (a global
  list in `config.yaml`) in `config.py` and `leash.capability_roots`. Task
  `allowed_paths` are bounded by `task_envelope_errors` against slice
  `target_paths`, else the global roots (default `src/**`, `tests/**`,
  `docs/spec/**`).
- **Slice `target_paths` is dead code.** `process/schemas/slice.schema.yaml` has
  `additionalProperties: false` and no `target_paths`, so the branch in
  `leash.task_envelope_errors` that reads it never fires. Every baseline task
  was bounded by `src/**` alone.
- **`related_capabilities` is read by nobody.** Routing asks the model for it;
  only `artifact_codec` knows the key. No read bound, spec scope or check uses it.
- **A rewind edge already exists:** `verifying → analyzing` in
  `ALLOWED_CHANGE_TRANSITIONS`. There is none from `specified` or `decomposed`.
- **Corpus:** M01 and M03 have one capability each; M02 has three that share
  `src/ratelimit`; J03 (judge pack pending) has 7 capabilities over three
  disjoint service roots (`document-service` ×4, `workflow-service` ×2,
  `audit-service` ×1) and leaves `shared-contracts/` owned by nobody.

---

## 1. DECISION

**D — ownership, not vocabulary.** Under-routing is judged by the Core through
the code ownership the catalog already declares, and it is stopped at the one
place the FSM can already send a Change back: the `converged` gate. Phase 1
ships the settled detector as a metric only (T9). Phase 2 turns the same
function into a `converged`-gate check. An unambiguous touch of an unrouted
capability means the Change does not converge; the Core takes the existing
`verifying → analyzing` edge and records the reason. The model then re-routes
in Analyze, where `routing.yaml` is inside its envelope. The new slice goes
through Specify, so the human sees the added domain at the Human Gate. No
lexical gate and no embedder enter Core now. An embedder does not enter Core
at all under this decision. A lexical ranker is kept as an offline experiment
(falsifier 6) and could at most become a receipt signal, never a gate. The
reason: the one thing that must never happen is a Change that silently
converges with a spec domain its code changed. That is closed
deterministically, with no new dependency, no new FSM edge and no gate a weak
model faces during Analyze. Earlier prevention is only paid for if the
detector shows the rewinds are frequent.

## 2. MECHANISM

**Ownership map** (new, `core/ownership.py`, pure functions):

- `capability_code_roots(product_root) -> dict[cap, list[root]]` reads
  `docs/spec/_capabilities.yaml` via `integrity.load_capability_catalog`.
  - Each root is normalised to a path prefix: `src/ratelimit` and
    `src/ratelimit/**` both become `src/ratelimit/`; `document-service` becomes
    `document-service/`.
  - `test_roots` are ignored: tests are shared, and every baseline task wrote
    `tests/**`.
- `owners(path) -> frozenset[cap]` returns every capability whose root is a
  prefix of `path`. It can return 0, 1 or many.
- `routed_capabilities(change) -> set[cap]` is the union of
  `primary_capability` and `related_capabilities` over all claims in
  `routing.yaml`. This is the first reader `related_capabilities` has ever had,
  and it is what makes the field mean something.

**Detector** — `under_routing(change_path, product_root, base) -> dict`:

1. Touched code paths come from `leash.git_dirty_paths` against the Change's
   base commit: the commit of the first `analyzing` transition receipt. Keep
   only paths under the global code roots, excluding interpreter caches (they
   are already exempt in leash) and `docs/**`.
2. Classify each path:
   - `covered`: `owners ∩ routed ≠ ∅`;
   - `unrouted`: `owners ≠ ∅` and `owners ∩ routed = ∅` — the defect;
   - `unowned`: `owners = ∅` — the catalog is incomplete. This is the human's
     catalog problem, not routing's; it is recorded, never gated.
3. Resolution: the share of covered paths with `len(owners) > 1`. This is how
   blind the check is on this catalog. On M02 it is 1.0: all three capabilities
   own every path, so a claim routed to any one covers everything. The
   detector does not abstain; it states its resolution.
4. Returns
   `{"unrouted": {cap: [paths]}, "unowned": [paths], "resolution": float, "measurable": bool}`.
   `measurable` is false when the catalog declares no per-capability
   `code_roots`, or when there are no touched code paths (docs route).

**Where it is recorded:**

- Phase 1: `deltafuse evidence` for `verification` (the `run.yaml` the Core
  already stamps) gains `ownership: {...}` with the dict above.
- The bench runner (`deltafuse-bench/qualify/qualify.py`) replaces
  `under_routing_rate: None` with:
  - `under_routing_rate` = changes with a non-empty `unrouted` ÷ measurable
    changes;
  - `ownership_resolution` (mean) next to it;
  - `unowned_paths`.

**Phase 2 gate:**

- `check_gate(change, "converged")` refuses when `unrouted` is non-empty.
- The queue maps that refusal to `advance --gate analyzing` (the existing
  edge). The transition receipt carries `reason: "under-routed"` and
  `capabilities: [...]`.
- `next_analyze_pass` learns one rule: when the last receipt into `analyzing`
  has `reason: under-routed`, it returns the `routing` pass even though
  `routing.yaml` exists, with the missing capabilities in `reason`. Slices,
  Specify and so on then follow as usual.

**Worker text:**

- `analyze` gains one sentence. When a claim's implementation must change code
  owned by another capability (its `code_roots` in the catalog), list that
  capability in `related_capabilities`.
- Nothing else. The model already reads the catalog in the routing pass.

**Dead code:** the `target_paths` branch in `leash.task_envelope_errors` is
removed. Neither the schema nor any skill can produce the key.

## 3. COST

- **Dependencies:** none.
- **Core surface:**
  - one module of about 120 lines;
  - one field in verification evidence;
  - one refusal in the `converged` gate;
  - one rule in `next_analyze_pass`;
  - no new FSM edge, halt kind or artifact.
- **Worker instruction:** about 35 words, roughly 50 tokens, in `analyze`
  (786 → about 820 words). This is noise against the 64k budget.
- **New gates:** one, phase 2 only, at `converged`. The bucket is "Core
  fixes": the Core routes the Change back, and the model does not retry the
  gate. The model's work happens in the next Analyze routing pass, a normal
  step with its own gate. The human re-accepts the widened spec at Specify,
  which is already a human halt, so no new halt kind is added.
- **What it costs instead of retries:** wasted Implement work on every rewind.
  That is measured, not argued; see falsifiers 1–2.
- **T3:** unaffected by the detector. Phase 2 adds retries only if the
  re-routing pass itself fails, and that is counted separately in
  `by_stage.analyze`.

## 4. REJECTED

The runner-up is **C (detector alone, fix the skill)**. It lost because the
audit showed the detector alone leaves the silent path open: a Change can
still converge and archive while its code changed a capability whose spec was
never touched. The only thing that stops that today is a human reading the
diff. Once the detector exists, closing that path costs one gate refusal and
one queue rule, reusing an edge the FSM already has. Leaving it open to save
that surface is the wrong trade. **A (lexical gate)** lost more clearly:

- it adds a gate at Analyze, the stage already spending most of T3 on format
  retries (13 in M03);
- it targets a failure nobody has observed;
- its false positives land on a weak model that cannot argue with a ranking.

## 5. FALSIFIERS

Measurable cases are those with at least two capabilities on disjoint
`code_roots` and a request that reaches the second one only implicitly. The
current corpus has none: M01 and M03 are single-capability, M02 has resolution
1.0, and J03 has disjoint service roots but no judge pack yet. Card zero is
therefore a bench case, or finishing J03's pack.

1. **Rate that keeps D.** Run the phase-1 detector over **N = 20** changes on
   measurable cases, on the pinned reference model. Cost is about $0.70 per
   run, so about $14.
   - If `under_routing_rate < 5%` (0 or 1 of 20): D stands, and phase 2 is
     optional.
   - If it is **5–20%**: ship phase 2 as decided.
   - If it is **≥ 20%** (4 or more of 20): rewinds after Implement are too
     expensive, and prevention must move earlier, to A as a routing-input
     candidate list. Go to falsifier 6.
2. **Rewind cost.** With phase 2 on, compare the median cost and wall-clock of
   rewound changes with unrewound ones. If a rewind costs more than **1.5×** a
   clean run on average, earlier prevention wins even at a 5–20% rate.
3. **False rewinds.** Of the rewinds, how many does a human judge legitimate
   (the code really did change that capability's behaviour)? If under **70%**,
   the catalog's roots are too coarse. The fix is catalog guidance, not
   routing, and phase 2 goes back to observe-only.
4. **Worker text cost.** Run the same measurable cases on the commit before
   and after the analyze sentence. If median `by_stage.analyze` retries rise by
   **≥ 1**, revert the sentence. The Core check does not depend on it.
5. **Resolution.** If mean `ownership_resolution ≥ 0.5` across the qualifying
   corpus, path ownership is too coarse to judge routing. That reopens settled
   item 3 (the detector design) towards file-level ownership.
6. **Lexical ceiling (free, offline).** Score a BM25 or term-overlap ranker
   using claim text against capability `summary`, `responsibility`,
   `entities`, `events`, over every recorded `request.md` plus the final true
   capability set (routing plus detector findings). If top-3 recall is below
   **90%**, A is dead regardless of falsifier 1. If it is at least 90% and
   falsifier 1 came out at 20% or more, A enters as a candidate list in the
   routing pass input, recorded in the receipt, not a gate.

## 6. UNKNOWNS

- **Undetectable under-routing.** A change of capability X's behaviour made
  entirely through code owned by a routed capability touches no X path. No
  path-based method sees it. I assumed it is rarer than the detectable kind,
  because behaviour tends to live where its code lives. The hidden oracle
  suites are the only judge of it.
- **The base commit.** I assumed the commit at the first `analyzing` receipt
  is the right diff base. The runner commits per worker step, so it exists,
  but it has not been verified for hosts that squash.
- **Root syntax.** Roots in catalogs appear as bare directories
  (`document-service`) and as directory paths (`src/ratelimit`). I assumed
  prefix semantics for both, and that no catalog uses mid-path globs. The
  capability schema does not constrain this.
- **Unowned code.** `shared-contracts/` in J03 belongs to no capability. I
  assumed recording it without gating is right. If unowned touches turn out to
  be most of the traffic, the catalog, not routing, is the weak artifact.
- **Re-routing in practice.** Whether a weak model re-routes correctly given
  the missing capability's name is unmeasured. The routing pass has never run
  with an existing `routing.yaml` to amend.
- **Interaction with roadmap item 1.** If `routing.yaml` moves to the Artifact
  Writer, the re-routing pass becomes an `update`, not a rewrite. Tier 2
  should order this after, or independent of, that change.

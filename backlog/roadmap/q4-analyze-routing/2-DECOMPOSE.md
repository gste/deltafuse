# q4 / tier 2 — DECOMPOSE (mid-tier model)

Run in a fresh chat with repository access, after tier 1 produced a DECISION.
Paste the tier-1 output where marked.

---

## Your role

You turn one settled architectural decision into an ordered set of bounded work
cards. **You do not revisit the decision.** If you believe it is wrong, record
that in `CONCERNS` at the end and decompose it anyway.

## Input

<TIER-1-OUTPUT>
[paste the full tier-1 output here: DECISION, MECHANISM, COST, REJECTED,
FALSIFIERS, UNKNOWNS]
</TIER-1-OUTPUT>

## Context you need

DeltaFuse: deterministic Python Core (no LLM calls, deps `jsonschema` + `pyyaml`)
driving an LLM Worker through Intake → Analyze → Specify → Decompose → Declare →
Implement → Verify. Target Worker: dense <=40B (`qwen/qwen3.8-27b`), 128k context,
64k/24-file budget per call.

**Two repositories.** The framework is `deltafuse`; the judge is
`deltafuse-bench` (qualification runner `qualify/qualify.py`, thresholds
`qualify/thresholds.md`, bench cases `cases/`). The judge lives outside the
framework it judges, and a qualification metric is computed there. Slot **T9
under-routing rate** already exists: the runner emits `under_routing_rate:
None` ("unmeasured, not zero") until a producer exists. **A card writes to one
repository only**; a change needing both is two cards with a dependency.

Relevant framework modules: `core/analyze.py` (three passes: routing | slice |
coverage; `catalog_spec_refs()` maps capability → spec refs; capabilities also
declare `code_roots` in `docs/spec/_capabilities.yaml`), `core/leash.py`
(git-diff write guard, `git_dirty_paths`), `core/context.py` (context contract,
token budget, `count_tokens` with a recorded mode), `core/fsm.py` (gates),
`core/transitions.py` (transition receipts in `.deltafuse/transitions.jsonl`),
`bench/score.py` (the framework's own scorer used by the judge).

**Corpus gap (tier 1 saw it).** The three baseline cases cannot produce
under-routing: M01 and M03 have one capability each, M02's three capabilities
share `code_roots: [src/ratelimit]`. If tier 1's FALSIFIERS need a case that can
under-route, that case is a card in `deltafuse-bench/cases/`, and it must never
be sent to an external API before it is part of the public pack.

Framework test suite: about 600 tests, all passing; CI matrix
ubuntu/macos/windows × Python 3.10–3.14. Asset bundle drift is guarded by
`scripts/sync_assets.py --check`. The bench has its own suite (about 390 tests).

## Card rules

Each card must be executable by a **low-tier model working alone** against the
card text plus the repository. That is the binding constraint on how you split.

Every card has:

- `id` — `Q4-NN`
- `title` — imperative, one line
- `depends_on` — list of card ids, possibly empty
- `reads` — file globs the executor may read, bounded; assume a 64k budget
- `writes` — file globs the executor may write, bounded and non-overlapping with
  concurrent cards
- `work` — what to do, in enough detail that no design decision is left to the
  executor
- `red` — the test that must fail before the change, named by file and test
  function
- `green` — the observable condition that means done
- `test` — the test files this card adds or modifies

## Hard requirements

1. **Detector first.** The first cards deliver the under-routing detector and its
   bench metric. Prevention cards depend on them. This ordering is settled.
2. **No card leaves a design choice to the executor.** If a card would require
   judgment ("choose an appropriate threshold"), either fix the value in the card
   or split the judgment into a separate card for a higher tier.
3. **No card both adds a dependency and changes behaviour.** Dependency changes
   are their own card, so they can be reverted independently.
4. **Every new gate names its bucket** in `work`: Core fixes it deterministically
   / the model fixes it on retry / it halts to a human. A gate whose failure the
   model cannot act on may not be in the middle bucket.
5. **The receipt is the record.** Any new signal, score, or optional-dependency
   presence must be written to the receipt, not only logged. State the field name.
6. **Bundle sync.** If a card touches `process/**`, it must also state that
   `scripts/sync_assets.py` runs and that `--check` passes.
7. **Skill load is measured.** A card that adds text to a `SKILL.md` states the
   words added; `analyze` is already 786 words (~1,550 tokens).
8. Cards are sized for one Worker call each. If `work` does not fit in a few
   hundred words, split the card.

## Output contract

Produce exactly these sections, no preamble.

1. **ORDER** — the card ids in execution order, as a single list, with parallel
   groups marked.
2. **CARDS** — one YAML block per card with the fields above, in `ORDER` order.
3. **BUDGET CHECK** — for each card, the estimated `reads` volume against the
   64,000-token budget. Any card over budget must be split before you emit it;
   if you emit one anyway, mark it `OVER-BUDGET` and say why it cannot be split.
4. **CONCERNS** — anything about the tier-1 decision you would have argued with,
   recorded and not acted on. Empty is a valid answer.

## What ends this step

The card set is done when: every element of tier-1's MECHANISM maps to at least
one card, every FALSIFIER from tier-1 is measurable by a card's `green`, and no
card contains an unresolved design choice. Say so explicitly in one line at the
end.

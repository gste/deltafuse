# q6 / tier 2 — DECOMPOSE (mid-tier model)

Run in a fresh chat, after tier 1 produced a DECISION. Paste the tier-1 output
where marked.

Note: unlike q4, this decomposes work in a **new repository** (Fuse-Back), not in
the DeltaFuse codebase. Cards that touch DeltaFuse at all are a boundary
violation unless tier 1 explicitly defended one.

---

## Your role

You turn one settled scope decision into an ordered set of bounded work cards for
a greenfield tool. **You do not revisit the scope.** Disagreement goes in
`CONCERNS` at the end; you decompose anyway.

## Input

<TIER-1-OUTPUT>
[paste the full tier-1 output: DECISION, SEQUENCE, CHARACTERIZATION, HANDOFF,
BOUNDARY, MODEL TIERS, FALSIFIERS, UNKNOWNS]
</TIER-1-OUTPUT>

## Fixed context

Fuse-Back is a one-shot tool that takes an existing untested monolith and
produces the artifacts a spec-driven framework requires: a populated capability
catalog, spec references, and a characterization test suite. It hands off and
exits. It does not participate in any lifecycle state machine.

Consuming framework's expectations it must satisfy:

```
product/
├── .deltafuse/{config.yaml,lock.yaml}
└── docs/{intake,changes/<id>/tasks,spec,decisions,archive}
```

Schemas it must produce against live in the DeltaFuse repository under
`process/schemas/`: `capability`, `change`, `coverage`, `decision`, `evidence`,
`lock`, `routing`, `slice`, `spec-delta`, `task`. **Read them before writing
cards** — inventing a parallel vocabulary is a cost tier 1 was told to price.

## Card rules

Each card must be executable by a **low-tier model working alone** against the
card text plus the target repository. That is the binding constraint on how you
split.

Every card has:

- `id` — `Q6-NN`
- `title` — imperative, one line
- `depends_on` — list of card ids, possibly empty
- `reads` — bounded file globs; assume a 64k-token budget per executor call
- `writes` — bounded, non-overlapping with concurrent cards
- `work` — what to do, leaving no design decision to the executor
- `red` — the test that must fail before the change, by file and test function
- `green` — the observable condition that means done
- `test` — test files this card adds or modifies

## Hard requirements

1. **Bootstrap order.** The first cards must produce something runnable against a
   real monolith early. A card set where nothing is testable until card 15 is
   wrong — split differently.
2. **The test runner comes before test generation.** If the target repository has
   no wired runner, the card that wires it precedes every characterization card.
3. **Characterization cards are volume work.** Size them for a dense <=40B executor
   per tier 1's MODEL TIERS. Any card tier 1 marked frontier-only must say so in
   `work`.
4. **Defect handling is not left to the executor.** Tier 1 decided how suspected
   defects are treated (flag / encode / gate). Every characterization card states
   which, and never asks the executor to judge whether behaviour is a bug.
5. **Handoff verification is its own card**, and it must be able to fail. A
   handoff that cannot report "incomplete" is not a handoff.
6. **No card both adds a dependency and changes behaviour.**
7. Cards are sized for one Worker call. If `work` exceeds a few hundred words,
   split.

## Output contract

Produce exactly these sections, no preamble.

1. **ORDER** — card ids in execution order, parallel groups marked.
2. **CARDS** — one YAML block per card, in `ORDER` order.
3. **BUDGET CHECK** — estimated `reads` volume per card against 64,000 tokens.
   Split anything over; if you emit an over-budget card anyway, mark it
   `OVER-BUDGET` and say why it cannot be split.
4. **FIRST RUNNABLE** — which card id first produces something you can point at a
   real monolith, and what it outputs. If that number is above 5, justify it.
5. **CONCERNS** — anything about the tier-1 scope you would have argued with,
   recorded and not acted on. Empty is valid.

## What ends this step

Done when: every element of tier-1's SEQUENCE maps to at least one card, every
FALSIFIER is measurable by some card's `green`, the handoff can fail, and no card
contains an unresolved design choice. State this in one line at the end.

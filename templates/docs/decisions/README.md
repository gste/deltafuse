# Architecture Decision Records (ADR)

Index of architecture decisions.

| Number | Title | Accepted | Date |
|--------|-------|:--------:|------|
| [0000](./0000-template.md) | Decision Template | `false` | YYYY-MM-DD |

## Rules & Lifecycle

| State | Who sets | Meaning & Next Step |
|---|:---:|---|
| `accepted: false` | AI Agent | Open draft with multiple options. Awaiting human decision. |
| `accepted: true` | **Human Only** | Decision made (Option 1, Option 2, or custom Option 3 specified in Decision Outcome). Trigger for `/audit-spec` to mirror into `docs/spec/`. |

## Key Invariants
1. **Human Gate:** Only a human may switch `accepted: false` to `accepted: true` (verified by `git log`).
2. **Mirroring to Law:** An accepted ADR (`accepted: true`) must be mirrored into `docs/spec/` as binding imperative text (via `/audit-spec`).

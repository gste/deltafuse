# Architecture Decision Records (ADR)

Index of architecture decisions.

| Number | Title | Status | Date |
|--------|-------|--------|------|
| [0000](./0000-template.md) | Decision Template | draft | YYYY-MM-DD |

## Status Lifecycle & Cheat-sheet

| Status | Who sets | Meaning & Next Step |
|---|:---:|---|
| `proposed` | AI Agent / Human | Initial proposal/draft. Open for human review. |
| `accepted` | **Human Only** | Approved architecture choice. Trigger for `/audit-spec` to mirror into `docs/spec/`. |
| `rejected` | **Human Only** | Rejected option. Decision reasoning is kept for historical context. |
| `superseded` | **Human Only** | Replaced by a newer decision (`superseded by ADR-NNNN`). |

## Key Rules
1. **Human Gate:** Only a human may set status to `accepted` or `rejected` (verified by `git log`).
2. **Mirroring to Law:** An `accepted` ADR must be mirrored into `docs/spec/` as binding imperative text (via `/audit-spec`).

# Small-LLM Quality Contract

[**English**](small-llm-contract.md) | [Русский](small-llm-contract.ru.md)

Normative for the framework (V3-FIX-020). The program-level history lives in
`backlog/product/v3/`; this document is the canonical specification.

## Reference frame

- The reference lower-bound Worker class is a local 35B-class A3B LLM. The
  first qualification model is `ornith-1.5-35b-a3b` served by LM Studio. No
  cloud or larger model is required for a correct Process run.
- A full Worker call must fit a **32k token** context window (qualification
  window).
- Framework-controlled input is bounded by default to **16,000 tokens and 24
  unique files** per call. The rest of the window is a mandatory reserve for
  host/system instructions, tool exchange, and the model's answer.

## Contract

- One Worker call solves one capability, one artifact layer, and one
  verifiable outcome.
- `next` passes exact bounded reads; no step requires loading the whole
  repository, all of `docs/spec/**`, or neighboring Changes.
- The Core performs routing mechanics, transition checks, diff calculation,
  and evidence bookkeeping outside the model's prompt.
- Receipts, manifests, full journals, and long command outputs never enter
  the Worker context without an explicit diagnostic need; the Core returns a
  short structured summary.
- When a token/file budget is exceeded, the work is decomposed. Truncating
  mandatory context and silently continuing are forbidden.
- Quality is measured by the disk-based bench: correctness, completed stages,
  retries, context tokens, unique files, hallucinated paths, and envelope
  violations.
- Absolute numerical release thresholds for v3 (T1-T8, per run and for
  medians) are fixed in `backlog/product/v3/thresholds.md`; qualification
  runs are executed by `scripts/qualify.py`. Weakening any threshold requires
  a separate maintainer Decision recorded with the backlog program.

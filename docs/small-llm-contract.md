# Small-LLM Quality Contract

[**English**](small-llm-contract.md) | [Русский](small-llm-contract.ru.md)

Normative for the framework (V3-FIX-020). The program-level history lives in
`backlog/roadmap/`; this document is the canonical specification.

## Reference frame

- The reference lower-bound Worker class is a **dense model of up to 40B
  parameters**. Sparse/A3B models are not the reference: success on them is an
  acceptable side effect, not a qualification target.
- The first qualification model is **`qwen/qwen3.8-27b`** via OpenRouter — dense
  27B, 1M context, 32,768 max output, $0.10/$1.80 per MTok. It is chosen because
  it mirrors the production case the framework is built for: a corporate BYOK
  dense ~27B.
- The floor-edge secondary is **`qwen/qwen3-32b`** — dense 32B, 131,072 context,
  16,384 max output, $0.08/$0.28 per MTok. It sits at the 40B boundary and has
  the cheapest output in the class.
- A full Worker call must fit a **128k token** context window (qualification
  window). This ceiling comes from the production constraint, not from the
  model: the corporate BYOK deployment the framework targets caps context at
  128k, and raising it requires a formal request. The reference model's own
  window is larger (1M) — do not widen the qualification window to match it.
- Framework-controlled input is bounded by default to **64,000 tokens and 24
  unique files** per call. The rest of the window is a mandatory reserve for
  host/system instructions, tool exchange, and the model's answer.
- **The 64,000 figure is provisional.** It preserves the ~50% window ratio the
  previous 32k/16,000 pair used, and must be confirmed by the first
  qualification run: effective context is typically well below nominal, and
  cross-file reasoning degrades fastest as context grows.
- **The 24-file cap does not scale with the window.** It bounds cross-file
  reasoning, which is a cognitive limit rather than a token limit, and is the
  first thing to degrade when context grows. Raising it requires its own
  measurement.

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
  medians) are fixed in `backlog/roadmap/q0-qualification-baseline/thresholds.md`;
  qualification runs are executed by `scripts/qualify.py`. Weakening any
  threshold requires a separate maintainer Decision recorded with the roadmap.

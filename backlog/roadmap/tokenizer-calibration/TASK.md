# Tokenizer calibration — background task (low-tier model)

Run in a fresh chat with shell access on the maintainer's Windows machine
(Git Bash or PowerShell). This message is the whole prompt. It is an
independent task: it does not touch the DeltaFuse framework code.

---

## Why

DeltaFuse bounds what the framework itself feeds a model per call (the
framework-controlled input) at about 64,000 tokens. That number is an
orientation for the size of one unit of work, not a hard limit. Without a
tokenizer the Core estimates tokens with a word heuristic, A03-01, in
`src/deltafuse/core/context.py`:

```
tokens ≈ ceil(words × factor),  words = len(text.split())
factor = max(suffix factor, script factor):
  EN prose 1.3 · Cyrillic 2.2 (any Cyrillic letter in the text) · code 2.7 ·
  YAML/JSON 4.5 · .log 4.8
```

A first check against one tokenizer showed Russian prose under-counted by 23 %.
Your job is to measure the heuristic against several real tokenizer families on
a real corpus and produce per-family calibration profiles. You collect numbers;
you do not change the framework.

## Hard rules

- **Do not modify anything in `C:/Users/ghost/workspace/gste/deltafuse` or
  `C:/Users/ghost/workspace/gste/deltafuse-bench`** except the results folder
  named below. No edits to `src/`, `tests/`, `process/`, `docs/`. No commits,
  no pushes.
- **Nothing leaves the machine except downloads of public tokenizer files.**
  All counting is local. The only exception is the optional Claude step below,
  which runs only when explicitly enabled and only on the DeltaFuse corpus.
- **Never accept a license, log in, or use someone else's token** to reach a
  gated repository. A gated or missing repository is skipped and recorded.
- **Never execute repository code** to load a tokenizer (`trust_remote_code`).
  If a family has no `tokenizer.json` loadable by the `tokenizers` library,
  skip it and record why.
- Never print API keys.

## Paths

- Work directory (venv, downloads, raw data):
  `%LOCALAPPDATA%/deltafuse/calibration/`
- Deliverables (the only place you write in the repositories):
  `C:/Users/ghost/workspace/gste/deltafuse/backlog/roadmap/tokenizer-calibration/results/`
- Framework source to import the heuristic from (read-only):
  `C:/Users/ghost/workspace/gste/deltafuse/src`
- Tokenizers already on disk — reuse, do not download again:
  `%LOCALAPPDATA%/deltafuse/tokenizers/Qwen_Qwen3.8-27B/tokenizer.json`,
  `%LOCALAPPDATA%/deltafuse/tokenizers/Qwen_Qwen3-32B/tokenizer.json`
  (each folder has `SOURCE` and `REVISION` files).

## Tokenizer families

Try the repositories in order; use the first that is public and has a
`tokenizer.json`. Record the repository actually used and its commit sha
(`huggingface_hub.HfApi().model_info(repo).sha`).

| family           | primary                                | alternates                                                                 | status       |
| ---------------- | -------------------------------------- | -------------------------------------------------------------------------- | ------------ |
| `qwen3.8`        | local `Qwen_Qwen3.8-27B`               | —                                                                          | done         |
| `qwen3`          | local `Qwen_Qwen3-32B`                 | —                                                                          | done         |
| `llama3`         | `meta-llama/Llama-3.1-8B-Instruct`     | `unsloth/Llama-3.1-8B-Instruct`, `NousResearch/Meta-Llama-3.1-8B-Instruct` | done         |
| `mistral-tekken` | `mistralai/Mistral-Nemo-Instruct-2407` | `mistralai/Mistral-Small-3.1-24B-Instruct-2503`                            | done         |
| `deepseek-v3`    | `deepseek-ai/DeepSeek-V3`              | —                                                                          | done         |
| `glm`            | `zai-org/GLM-4.5`                      | `THUDM/glm-4-9b-chat-hf`                                                   | done         |
| `gemma3`         | `google/gemma-3-27b-it`                | `unsloth/gemma-3-27b-it`                                                   | done         |
| `openai-o200k`   | `tiktoken` encoding `o200k_base`       | —                                                                          | done         |
| `openai-cl100k`  | `tiktoken` encoding `cl100k_base`      | —                                                                          | done         |
| `claude`         | optional, see below                    | —                                                                          | skipped      |

Download only `tokenizer.json` (`huggingface_hub.hf_hub_download(repo,
"tokenizer.json")`). Count with `tokenizers.Tokenizer.from_file(...)` and
`encode(text, add_special_tokens=False)`; for `tiktoken`, `encode(text,
disallowed_special=())`.

**Claude (optional).** Run only if both `ANTHROPIC_API_KEY` and
`CALIBRATE_CLAUDE=1` are set. Use the Messages `count_tokens` endpoint with
model `claude-opus-5`, one user message holding the file text, and subtract the
count for an empty-text message to remove framing. Only files from the
DeltaFuse repository — never `deltafuse-bench` (it holds hidden test suites)
and never `EXTRA_CORPUS`. Otherwise record `claude` as skipped: "not enabled".

## Corpus

Collect UTF-8 text files, skip anything that is not valid UTF-8, larger than
1 MB, or shorter than 20 words, and drop exact duplicates by sha256.

From `C:/Users/ghost/workspace/gste/deltafuse`:
- `docs/**/*.md`, `backlog/roadmap/**/*.md`, `process/**/*.md`
- `process/**/*.yaml`, `process/**/*.json`
- `src/deltafuse/**/*.py` **excluding** `src/deltafuse/assets/**` (a generated
  copy of `process/**`)
- `tests/**/*.py`

From `C:/Users/ghost/workspace/gste/deltafuse-bench`:
- `cases/**/*.md`, `cases/**/*.yaml`, `cases/**/*.json`, `cases/**/*.py`

Logs, from `%LOCALAPPDATA%/deltafuse/runs/`:
- `*.log`, `**/sandbox/.deltafuse/*.jsonl` — take at most 30 files.

`EXTRA_CORPUS`: if the environment variable is set, it is a `;`-separated list
of extra directories the maintainer chose (e.g. work repositories). Include
`*.md`, `*.py`, `*.java`, `*.kt`, `*.ts`, `*.yaml`, `*.yml`, `*.json` from them.
These are counted locally only.

## Classification — use the framework's own rule

Import the heuristic from the framework and classify each file exactly as the
Core does, so the calibration targets the real categories:

```python
import sys; sys.path.insert(0, r"C:/Users/ghost/workspace/gste/deltafuse/src")
from deltafuse.core import context as c
factor = c.token_factor(text, path)
category = {c.WORD_FACTOR_EN: "en", c.WORD_FACTOR_CYRILLIC: "cyrillic",
            c.WORD_FACTOR_CODE: "code", c.WORD_FACTOR_YAML: "yaml",
            c.WORD_FACTOR_LOG: "log"}[factor]
```

Per file also record `cyrillic_share` = Cyrillic letters / all letters (0 when
there are no letters) and `suffix`.

## What to compute

Write one script, `calibrate.py`, and do all counting in it — never count by
hand. Per file and per available tokenizer, one row:

`source, path, suffix, category, cyrillic_share, words, bytes, tokenizer, tokens,
tokens_per_word, tokens_per_kbyte, heuristic_tokens`

where `heuristic_tokens = ceil(words × factor)`.

Aggregates:

1. Per `(category, tokenizer)`: `n_files`, median / p10 / p90 of
   `tokens_per_word`, median `tokens_per_kbyte`, and the current heuristic's
   error = `factor / median_tokens_per_word − 1`.
2. Per `category`: the proposed factor = median over tokenizers of their
   median `tokens_per_word`; min and max of those medians; the current factor.
3. The Cyrillic rule: for files the Core calls `cyrillic`, the median
   `tokens_per_word` per tokenizer in three buckets of `cyrillic_share`:
   `< 0.1`, `0.1–0.5`, `> 0.5`. (The rule fires on any single Cyrillic letter;
   this shows whether mostly-English files are overcounted.)
4. `.jsonl` files: report their category and error separately — the Core has
   no suffix rule for them.
5. Neutral unit: per category, the spread (max/min across tokenizers) of
   `tokens_per_word` versus of `tokens_per_kbyte`. This informs the open
   roadmap question of expressing the budget in bytes instead of tokens.

## Deliverables

In the results folder:

- `calibrate.py` — the script, runnable again.
- `samples.csv` — every row above.
- `summary.md` — the aggregates as tables, the list of families used with
  repository and sha, the list of skipped families with reasons, and corpus
  size (files and words per source and category).
- `profiles.yaml` — exactly this shape:

```yaml
schema_version: 1
generated: <ISO-8601 UTC>
heuristic_measured: a03-01
corpus: {files: <n>, words: <n>, sources: [deltafuse, deltafuse-bench, runs, extra]}
default:                       # median across families
  factors: {en: 0.0, cyrillic: 0.0, code: 0.0, yaml: 0.0, log: 0.0}
  spread:  {en: [0.0, 0.0], cyrillic: [0.0, 0.0], code: [0.0, 0.0], yaml: [0.0, 0.0], log: [0.0, 0.0]}
families:
  qwen3.8:
    source: Qwen/Qwen3.8-27B
    revision: <sha>
    factors: {en: 0.0, cyrillic: 0.0, code: 0.0, yaml: 0.0, log: 0.0}
    n_files: {en: 0, cyrillic: 0, code: 0, yaml: 0, log: 0}
skipped:
  - {family: <name>, reason: <text>}
models:                        # model-id prefix -> family, fixed by the maintainer
  "qwen/qwen3.8": qwen3.8
  "qwen/": qwen3
  "meta-llama/llama-3": llama3
  "mistralai/": mistral-tekken
  "deepseek/": deepseek-v3
  "z-ai/glm": glm
  "google/gemma-3": gemma3
  "openai/gpt-4o": openai-o200k
  "openai/gpt-5": openai-o200k
  "openai/gpt-4": openai-cl100k
  "anthropic/": claude
```

Round factors to two decimals. A category with fewer than 5 files for a family
gets `null` for that family and is excluded from `default`.

## Procedure

1. Create a venv in the work directory; install `tokenizers`,
   `huggingface_hub`, `tiktoken`, `pyyaml` (and `anthropic` only if the Claude
   step is enabled). Do not install into any repository's venv.
2. Write `calibrate.py`. Run it once on 5 files and 2 tokenizers; check the
   rows look sane (tokens > 0, categories as expected).
3. Run it fully.
4. Write `summary.md` and `profiles.yaml` from the script's output.
5. Report.

## Stop conditions — report instead of continuing

- More than half of the families end up skipped.
- A tokenizer needs code execution, a login or a license acceptance and no
  listed alternate works — skip that family; stop only under the rule above.
- Anything would require editing framework or bench files outside the results
  folder.
- The corpus has fewer than 200 files after filtering.

## Report (your final message)

1. **STATUS** — `DONE` or `BLOCKED`.
2. **FAMILIES** — used (repository, sha) and skipped (reason).
3. **CORPUS** — files and words per source and per category.
4. **HEADLINE** — the per-category table: current factor, proposed factor,
   spread across families, current heuristic error per family.
5. **FINDINGS** — at most five, each with its number: e.g. the Cyrillic bucket
   result, `.jsonl` handling, words-versus-bytes spread.
6. **BLOCKER** — only if `BLOCKED`: which stop condition and the evidence.

Do not propose code changes to the framework. The maintainer decides what to
do with the numbers.

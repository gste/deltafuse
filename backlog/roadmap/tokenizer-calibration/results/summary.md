# Tokenizer calibration — heuristic A03-01 measured on 9 tokenizer families

**STATUS: DONE** — 9 of 10 families measured, 1 skipped, 281 files counted once per family (2,529 rows). No stop condition met: fewer than half the families were skipped and the corpus is above the 200-file floor.

## 1. Method

- One shared harness, `calibrate.py`, collects the corpus, classifies every file with the framework's own rule (`deltafuse.core.context.token_factor`, A03-01) and counts tokens. Nothing was counted by hand.
- The corpus was frozen once into `corpus.csv` (281 files) and every family was measured against that identical manifest, so cross-family columns are differences between tokenizers and nothing else.
- The build kept 281 files of 323 in-scope candidates: 38 dropped for being under 20 words, 4 exact duplicates by sha256, 0 non-UTF-8, 0 over 1 000 000 bytes.
- Counting: `tokenizers.Tokenizer.from_file(...).encode(text, add_special_tokens=False)`, `tiktoken.encode(text, disallowed_special=())`. Only `tokenizer.json` was downloaded; no repository code was executed, no login, no license acceptance.
- `median` is the 50th percentile; `p10`/`p90` use linear interpolation between closest ranks. `heuristic error = current factor / median tokens-per-word - 1`, so a **negative** error means the heuristic feeds the model **less** than reality (undercount, budget risk) and a positive one means it over-feeds (wasted budget).
- One subagent per family row of the task's table ran exactly one tokenizer; each wrote its own folder `results/<family>/{samples.csv,meta.json,report.md}` including its own verification of row counts, non-zero tokens and a direct library re-count.

## 2. Families

| family | status | repository actually used | revision | files |
| --- | --- | --- | --- | --- |
| `deepseek-v3` | used | `deepseek-ai/DeepSeek-V3` | `e815299b0bcb` | 281 |
| `gemma3` | used | `unsloth/gemma-3-27b-it` | `7a5a3053dbd5` | 281 |
| `glm` | used | `zai-org/GLM-4.5` | `cbb2c7cfb52f` | 281 |
| `llama3` | used | `unsloth/Llama-3.1-8B-Instruct` | `4699cc75b550` | 281 |
| `mistral-tekken` | used | `mistralai/Mistral-Nemo-Instruct-2407` | `04d8a90549d2` | 281 |
| `openai-cl100k` | used | `tiktoken:cl100k_base` | `cl100k_base-n_vocab-100277` | 281 |
| `openai-o200k` | used | `tiktoken:o200k_base` | `o200k_base-n_vocab-200019` | 281 |
| `qwen3` | used | `Qwen/Qwen3-32B` | `9216db5781bf` | 281 |
| `qwen3.8` | used | `Qwen/Qwen3.8-27B` | `1d4bf0f2ff60` | 281 |
| `claude` | **skipped** | - | - | 0 — not enabled |

Repositories tried and rejected before the one used (no license accepted, no login):

| family | rejected repository |
| --- | --- |
| `gemma3` | google/gemma-3-27b-it: gated, needs license acceptance: 401 Client Error. |
| `llama3` | meta-llama/Llama-3.1-8B-Instruct: gated, needs license acceptance: 401 Client Error. |

## 3. Corpus

| source | category (Core's own label) | files | words |
| --- | --- | --- | --- |
| deltafuse | en | 31 | 11,504 |
| deltafuse | cyrillic | 30 | 34,606 |
| deltafuse | code | 115 | 94,008 |
| deltafuse | yaml | 28 | 2,294 |
| deltafuse-bench | en | 23 | 5,641 |
| deltafuse-bench | code | 14 | 7,223 |
| deltafuse-bench | yaml | 25 | 13,625 |
| runs | en | 15 | 9,855 |
| **total** |  | **281** | **178,756** |

The `log` category is empty: `%LOCALAPPDATA%/deltafuse/runs/` holds 0 `*.log` files, so `WORD_FACTOR_LOG = 4.8` is **unmeasured by this campaign** — no evidence for or against it. `15` `.jsonl` run journals carry the whole runs source.

## 4. Headline — proposed factor per category

Proposed = median across families of each family's median tokens-per-word (categories with fewer than 5 files for a family are excluded); spread = min/max of those medians.

| category | current factor | proposed (median of families) | spread across families | mean error of current factor | error range across families |
| --- | --- | --- | --- | --- | --- |
| `en` | 1.3 | **1.75** | 1.72 – 1.88 | -26.8% | -31.0% … -24.6% |
| `cyrillic` | 2.2 | **2.27** | 2.12 – 2.72 | -3.3% | -19.0% … +4.0% |
| `code` | 2.7 | **2.86** | 2.81 – 3.46 | -8.7% | -21.9% … -3.8% |
| `yaml` | 4.5 | **3.08** | 3.02 – 3.52 | +42.5% | +27.7% … +49.2% |
| `log` | 4.8 | not measurable | - | - | - |

## 5. Aggregate — every (category, family) cell

| family | category | n files | median tok/word | p10 | p90 | median tok/kbyte | heuristic error |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `deepseek-v3` | en | 69 | 1.796 | 1.489 | 7.414 | 254.8 | -27.6% |
| `deepseek-v3` | cyrillic | 30 | 2.324 | 1.659 | 2.581 | 226.2 | -5.3% |
| `deepseek-v3` | code | 129 | 3.055 | 2.485 | 3.637 | 264.9 | -11.6% |
| `deepseek-v3` | yaml | 53 | 3.231 | 2.648 | 4.990 | 295.4 | +39.3% |
| `gemma3` | en | 69 | 1.884 | 1.601 | 9.219 | 266.3 | -31.0% |
| `gemma3` | cyrillic | 30 | 2.197 | 1.684 | 2.525 | 227.8 | +0.1% |
| `gemma3` | code | 129 | 3.456 | 2.769 | 4.212 | 299.4 | -21.9% |
| `gemma3` | yaml | 53 | 3.524 | 3.075 | 5.679 | 327.6 | +27.7% |
| `glm` | en | 69 | 1.731 | 1.503 | 7.554 | 243.2 | -24.9% |
| `glm` | cyrillic | 30 | 2.132 | 1.601 | 2.410 | 217.9 | +3.2% |
| `glm` | code | 129 | 2.817 | 2.300 | 3.329 | 243.8 | -4.2% |
| `glm` | yaml | 53 | 3.023 | 2.527 | 4.542 | 277.5 | +48.9% |
| `llama3` | en | 69 | 1.724 | 1.502 | 7.134 | 241.6 | -24.6% |
| `llama3` | cyrillic | 30 | 2.272 | 1.602 | 2.578 | 222.1 | -3.2% |
| `llama3` | code | 129 | 2.808 | 2.295 | 3.324 | 242.6 | -3.8% |
| `llama3` | yaml | 53 | 3.017 | 2.527 | 4.457 | 276.8 | +49.2% |
| `mistral-tekken` | en | 69 | 1.862 | 1.558 | 9.313 | 256.4 | -30.2% |
| `mistral-tekken` | cyrillic | 30 | 2.284 | 1.673 | 2.604 | 230.7 | -3.7% |
| `mistral-tekken` | code | 129 | 3.041 | 2.440 | 3.629 | 264.9 | -11.2% |
| `mistral-tekken` | yaml | 53 | 3.256 | 2.747 | 5.490 | 296.3 | +38.2% |
| `openai-cl100k` | en | 69 | 1.724 | 1.503 | 7.134 | 241.6 | -24.6% |
| `openai-cl100k` | cyrillic | 30 | 2.717 | 1.606 | 3.171 | 253.7 | -19.0% |
| `openai-cl100k` | code | 129 | 2.808 | 2.295 | 3.330 | 242.7 | -3.8% |
| `openai-cl100k` | yaml | 53 | 3.017 | 2.527 | 4.457 | 276.8 | +49.2% |
| `openai-o200k` | en | 69 | 1.733 | 1.505 | 7.250 | 244.3 | -25.0% |
| `openai-o200k` | cyrillic | 30 | 2.116 | 1.607 | 2.386 | 216.2 | +4.0% |
| `openai-o200k` | code | 129 | 2.855 | 2.324 | 3.316 | 245.0 | -5.4% |
| `openai-o200k` | yaml | 53 | 3.071 | 2.501 | 4.730 | 278.8 | +46.5% |
| `qwen3` | en | 69 | 1.754 | 1.511 | 9.113 | 249.3 | -25.9% |
| `qwen3` | cyrillic | 30 | 2.389 | 1.609 | 2.721 | 232.5 | -7.9% |
| `qwen3` | code | 129 | 2.846 | 2.307 | 3.404 | 247.7 | -5.1% |
| `qwen3` | yaml | 53 | 3.077 | 2.655 | 5.290 | 281.1 | +46.2% |
| `qwen3.8` | en | 69 | 1.800 | 1.561 | 9.179 | 261.2 | -27.8% |
| `qwen3.8` | cyrillic | 30 | 2.156 | 1.645 | 2.453 | 224.3 | +2.0% |
| `qwen3.8` | code | 129 | 3.044 | 2.462 | 3.638 | 264.6 | -11.3% |
| `qwen3.8` | yaml | 53 | 3.269 | 2.862 | 5.442 | 295.8 | +37.6% |

## 6. The Cyrillic rule, bucketed by how Cyrillic the file actually is

The Core routes a file to `cyrillic` (factor 2.2) on **any single** Cyrillic letter. Files below are those the Core labelled `cyrillic`, split by `cyrillic_share` = Cyrillic letters / all letters. Median tokens-per-word per family:

| family | share <0.1 | share 0.1-0.5 | share >0.5 |
| --- | --- | --- | --- |
| **files in bucket** | 13 | 3 | 14 |
| `deepseek-v3` | 1.784 | 2.485 | 2.464 |
| `gemma3` | 1.839 | 2.509 | 2.337 |
| `glm` | 1.708 | 2.345 | 2.284 |
| `llama3` | 1.708 | 2.446 | 2.447 |
| `mistral-tekken` | 1.790 | 2.453 | 2.464 |
| `openai-cl100k` | 1.710 | 2.830 | 3.043 |
| `openai-o200k` | 1.729 | 2.375 | 2.283 |
| `qwen3` | 1.742 | 2.496 | 2.609 |
| `qwen3.8` | 1.807 | 2.422 | 2.328 |
| **median of families** | 1.742 | 2.453 | 2.447 |

Mostly-Latin files that the rule still charges 2.2 for measure 1.74 tokens/word — the same as an ordinary English file — so the rule overcounts them by about +26%. Genuinely Russian files measure 2.45, so 2.2 is about right for them. A single Cyrillic letter moves a file from 1.3 to 2.2 while its real cost stays near 1.74, so the rule is not a script detector: on mixed files it is a 1.4x swing.

## 7. `.jsonl` — the suffix the Core has no rule for

All 15 run journals land in `en` (factor 1.3), because `.jsonl` is not in _YAML_SUFFIXES_ while `.json` is. Their measured density:

| family | n files | median tok/word | heuristic error | share of all `en` tokens |
| --- | --- | --- | --- | --- |
| `deepseek-v3` | 15 | 7.409 | -82.5% | 74% |
| `gemma3` | 15 | 9.183 | -85.8% | 77% |
| `glm` | 15 | 7.550 | -82.8% | 74% |
| `llama3` | 15 | 7.133 | -81.8% | 74% |
| `mistral-tekken` | 15 | 9.267 | -86.0% | 77% |
| `openai-cl100k` | 15 | 7.133 | -81.8% | 74% |
| `openai-o200k` | 15 | 7.250 | -82.1% | 74% |
| `qwen3` | 15 | 9.067 | -85.7% | 77% |
| `qwen3.8` | 15 | 9.133 | -85.8% | 77% |

## 8. Neutral unit — tokens-per-word versus tokens-per-kbyte

Spread across the 9 families of each category's median, per unit. A lower ratio means the unit travels better between tokenizers — the roadmap question of stating the budget in bytes instead of tokens.

| category | tok/word min – max | spread | tok/kbyte min – max | spread | more stable unit |
| --- | --- | --- | --- | --- | --- |
| `en` | 1.724 – 1.884 | 1.093 | 241.597 – 266.285 | 1.102 | words narrower |
| `cyrillic` | 2.116 – 2.717 | 1.284 | 216.2 – 253.665 | 1.173 | bytes narrower |
| `code` | 2.808 – 3.456 | 1.231 | 242.646 – 299.427 | 1.234 | words narrower |
| `yaml` | 3.017 – 3.524 | 1.168 | 276.832 – 327.637 | 1.184 | words narrower |

## 9. Robustness

| family | `en` excluding `.jsonl` | `yaml` excluding `.json` | `code` (all `.py`) |
| --- | --- | --- | --- |
| `deepseek-v3` | 1.685 (-22.9%) | 3.184 (+41.3%) | 3.055 (-11.6%) |
| `gemma3` | 1.748 (-25.6%) | 3.469 (+29.7%) | 3.456 (-21.9%) |
| `glm` | 1.628 (-20.2%) | 2.943 (+52.9%) | 2.817 (-4.2%) |
| `llama3` | 1.628 (-20.2%) | 2.935 (+53.3%) | 2.808 (-3.8%) |
| `mistral-tekken` | 1.732 (-25.0%) | 3.215 (+40.0%) | 3.041 (-11.2%) |
| `openai-cl100k` | 1.628 (-20.2%) | 2.935 (+53.3%) | 2.808 (-3.8%) |
| `openai-o200k` | 1.637 (-20.6%) | 2.974 (+51.3%) | 2.855 (-5.4%) |
| `qwen3` | 1.664 (-21.9%) | 3.037 (+48.2%) | 2.846 (-5.1%) |
| `qwen3.8` | 1.725 (-24.6%) | 3.237 (+39.0%) | 3.044 (-11.3%) |

Whole-corpus view, not median-per-file: actual tokens fed / heuristic estimate. This is what a 64 000-token budget would really have bought.

| family | `en` | `cyrillic` | `code` | `yaml` |
| --- | --- | --- | --- | --- |
| `deepseek-v3` | 3.42x | 1.01x | 1.13x | 1.80x |
| `gemma3` | 4.01x | 0.99x | 1.30x | 2.37x |
| `glm` | 3.37x | 0.95x | 1.04x | 1.85x |
| `llama3` | 3.27x | 0.99x | 1.04x | 1.73x |
| `mistral-tekken` | 3.98x | 1.02x | 1.13x | 2.21x |
| `openai-cl100k` | 3.27x | 1.15x | 1.04x | 1.73x |
| `openai-o200k` | 3.31x | 0.95x | 1.05x | 1.74x |
| `qwen3` | 3.86x | 1.04x | 1.06x | 2.18x |
| `qwen3.8` | 3.91x | 0.97x | 1.14x | 2.27x |

## 10. Caveats the maintainer should read before using these numbers

- **`log` is unmeasured** (0 files). `cyrillic` 30, `code` 129, `yaml` 53 files — those three carry weight. `en` is 69 files, of which 15 are `.jsonl` run journals.
- **`claude` was skipped: the gate is closed** (`ANTHROPIC_API_KEY` unset, `CALIBRATE_CLAUDE` unset, `anthropic` not installed). No request left the machine and the harness's Claude branch was never exercised, so it is unverified code.
- **The two local Qwen tokenizers the task told us to reuse are not on this machine**: `%LOCALAPPDATA%/deltafuse/tokenizers/` does not exist. The harness fell through to the public `Qwen/Qwen3.8-27B` and `Qwen/Qwen3-32B` repos and recorded their revision shas; no `SOURCE`/`REVISION` sidecars were available.
- **`mistral-tekken` is not Tekken.** The task allows only a `tokenizer.json` read by the `tokenizers` library, and Mistral ships a plain BPE re-encoding (`model.type=BPE`, ByteLevel). The agent recorded byte-level coverage with no UNK, so undercount risk is low, but greedy BPE drifts from Tekken max-match on dense JSON: treat this family as indicative.
- **`llama3` and `openai-cl100k` measure the same thing on Latin text.** They returned an identical token count on 232 of 247 Cyrillic-free files and differ mostly where Cyrillic is present (1 of 34 identical, Llama-3.1 about 20 % cheaper there). No other pair comes close: the next highest agreement in the whole matrix is `glm|openai-cl100k` at 132/281 (47%). Treat the nine families as about 8 independent draws for `en`/`code`/`yaml`, and do not average Cyrillic across those two as if they were independent.
- **One file drives the `yaml` token totals**: `dependencies.lock.json` alone is 73% of that category's tokens for the median family and reaches 15.4 tokens/word. The `yaml` *median* is robust to it, any token-weighted use is not.
- **`gemma3` is the outlier family on `code`** (3.46 tok/word against 2.81–3.06 for the other eight), and it is what widens the `code` spread; its prose numbers are mid-pack.
- `backlog/roadmap/tokenizer-calibration/results/**` was excluded from the corpus: counting this task's own output would make the file set depend on how many reports already existed. `TASK.md` itself is in scope.

## 11. Reproduce

```
cd %LOCALAPPDATA%/deltafuse/calibration
venv/Scripts/python.exe <results>/calibrate.py corpus
for f in qwen3.8 qwen3 llama3 mistral-tekken deepseek-v3 glm gemma3 \
         openai-o200k openai-cl100k claude; do
  venv/Scripts/python.exe <results>/calibrate.py run --family $f
done
venv/Scripts/python.exe <results>/calibrate.py summarize
```

`corpus.csv` is the frozen manifest; `samples.csv` is the merge of the per-family rows (2,529 = 9 x 281); `profiles.yaml` is the machine-readable profile; each `report.md` is one family's full detail including its own verification.

The maintainer-facing conclusions, in Russian, are in `REPORT.md` — it restates these numbers, it adds no measurement of its own.

This document was generated by `calibrate.py summarize` from `samples.csv` and the per-family `meta.json` files — no number was transcribed by hand. It proposes no changes to the framework; what to do with these factors is the maintainer's call.

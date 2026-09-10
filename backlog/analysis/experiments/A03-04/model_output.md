# Ответ локальной модели ornith-1.5-35b-a3b

- **Длительность инференса:** 421.35 с
- **Использование токенов:** {
  "prompt_tokens": 577,
  "completion_tokens": 2043,
  "total_tokens": 2620,
  "completion_tokens_details": {
    "reasoning_tokens": 1283
  }
}

## Reasoning Content

Let me analyze this carefully.

The question asks whether DeltaFuse validates the FULL prompt (including system instructions, role prompt, tool schemas, chat template, and completion reserve) against `max_tokens: 16000`, or only validates the loaded file contents.

Let me look at the code in `src/deltafuse/core/context.py`:

```python
def estimate_tokens(text: str) -> int:
    words = text.split()
    return math.ceil(len(words) * 1.3)

def estimate_files_tokens(files: list[Path]) -> int:
    total = 0
    for f in files:
        if f.is_file():
            try:
                content = f.read_text(encoding="utf-8", errors="ignore")
                total += estimate_tokens(content)
            except Exception:
                pass
    return total

def validate_context_budget(context_budget: dict[str, Any], files: list[Path]) -> list[str]:
    errors: list[str] = []
    max_files = context_budget.get("max_files")
    max_tokens = context_budget.get("max_tokens")

    if max_files is not None and len(files) > max_files:
        errors.append(f"Context budget exceeded: {len(files)} files loaded, maximum allowed is {max_files}")

    if max_tokens is not None:
        estimated = estimate_files_tokens(files)
        if estimated > max_tokens:
            errors.append(f"Context budget exceeded: estimated {estimated} tokens loaded, maximum allowed is {max_tokens}")

    return errors
```

Looking at `validate_context_budget`, it only takes `files` as input and estimates the tokens of those files. It does NOT take into account:
- system instructions
- role prompt
- tool schemas
- chat template
- completion reserve

So the answer is NO - it only validates the loaded file contents, not the full prompt.

Let me think about the evidence:

1. The `validate_context_budget` function signature only accepts `context_budget` and `files`. There's no parameter for system instructions, role prompt, tool schemas, chat template, or completion reserve.

2. The token estimation is based solely on file contents via `estimate_files_tokens(files)`.

3. The documentation says "Exceeding the context budget (max_tokens or max_files from .deltafuse/config.yaml) is treated as a design defect requiring finer decomposition." This implies the validation is about files loaded, not the full prompt overhead.

Now for the risks for a 35B local model:

A 35B local model typically has a context window of maybe 8K-32K tokens (e.g., some models support 32K). If `max_tokens` is set to 16000, and this only counts file contents, then the actual prompt sent to the model would be:

actual_prompt_tokens = file_tokens + system_instructions + role_prompt + tool_schemas + chat_template + completion_reserve

If file tokens are ~16000 (at budget), plus overhead of maybe 2000-4000 tokens for system/role/tools/template, the total could be 18000-20000 tokens. If the model's context window is only 16K or even less, this would cause:
- Context overflow / truncation
- The prompt being silently cut off
- Errors from the inference engine

For a local model specifically, you often have limited VRAM and fixed context windows. Exceeding them causes hard failures (OOM, truncation errors) rather than graceful degradation.

Also, there's a token estimation inaccuracy issue: `estimate_tokens` uses `len(words) * 1.3`, which is a very rough approximation. Tokenizers typically produce more tokens per word for code (especially with subword tokenization). For code, the ratio can be higher - maybe 1.5-2x or more depending on the tokenizer. So this underestimates actual tokens, making the budget check even less reliable.

Let me also note:
- The `errors="ignore"` in read_text could silently drop characters, affecting accuracy.
- The try/except with `pass` silently skips files that can't be read, so a file that fails to load doesn't count toward the budget but might still be loaded later (or its absence causes issues).

Let me structure my answer:

1. Direct Conclusion: No - only validates loaded file contents, not the full prompt overhead.

2. Evidence from code and docs:
- Code: `validate_context_budget` only accepts files, estimates tokens only from file contents via `estimate_files_tokens`. No parameters for system/role/tool/template/reserve.
- Docs: The Context Contract talks about "what an agent MUST, MAY, and MUST NOT read" - it's about file access, not prompt composition overhead.

3. Concrete Counterexample / Gap:
- If files sum to 16000 tokens (at budget), plus ~3000 tokens of system/role/tool/template/reserve = 19000 total. For a model with 16K context, this overflows.
- The word-based estimation undercounts code tokens.

4. Level of Certainty: High - the code is clear about what it validates.

Let me write this up clearly and concisely.

Actually, let me reconsider the token estimation issue more carefully. The function `estimate_tokens` does `len(words) * 1.3`. For English text, average tokens per word is around 1.2-1.5, so 1.3 is roughly reasonable for prose. But for code, subword tokenizers often produce MORE tokens than words (e.g., a single identifier like `calculateTotalPaymentAmount` might be split into multiple tokens). So the estimate likely underestimates code tokens significantly.

This compounds the problem: even the file content itself may be underestimated, and then there's no accounting for prompt overhead at all.

Let me finalize my answer with appropriate structure.


## Assistant Response

## 1. Direct Conclusion

**No.** DeltaFuse does **not** validate the full prompt against `max_tokens: 16000`. It validates **only the estimated token count of the loaded file contents**. System instructions, role prompt, tool schemas, chat template, and completion reserve are entirely outside the scope of `validate_context_budget`, so their token overhead is never subtracted from or accounted against the budget.

## 2. Evidence from Code and Docs

**Code evidence (`src/deltafuse/core/context.py`):**
- The entry point `validate_context_budget(context_budget, files)` accepts **only two arguments**: the budget dict and a list of file paths. There is no parameter for system prompt, role prompt, tool schemas, chat template, or completion reserve.
- Token accounting flows exclusively through `estimate_files_tokens(files)`, which sums `estimate_tokens(content)` over each loaded file's text. Nothing else contributes to `estimated`.
- The comparison `if estimated > max_tokens` therefore measures **file content only**, not the assembled prompt.

**Docs evidence (`docs/context-model.md`):**
- The Context Contract is defined around *what an agent reads* ("MUST, MAY, MUST NOT read") and file-level decomposition — i.e., it governs **input selection**, not prompt composition overhead.
- "Exceeding the context budget" is framed as a design defect requiring "finer decomposition," which again points at file/file-count management rather than full-prompt token accounting.

## 3. Concrete Counterexample / Gap

Assume an agent loads files that estimate to exactly **16,000 tokens** (right at the configured budget). The validator returns `[]` (no errors) and passes the gate. But the actual prompt sent to the model is:

```
actual_prompt = file_tokens(16,000)
              + system_instructions(~800)
              + role_prompt(~400)
              + tool_schemas(~1,500)
              + chat_template(~300)
              + completion_reserve(~1,000)
            ≈ 20,000 tokens
```

For a **35B local model** (commonly constrained to an 8K–16K context window with fixed VRAM), this produces:

- **Hard context overflow / truncation.** Local inference engines typically fail loudly on OOM or silently truncate the prompt — neither is caught by the gate, since the gate never knew about the ~4k overhead.
- **Silent quality collapse.** If truncated, the system/role/tool instructions may be dropped while file content survives, so the agent loses its operating contract mid-session.
- **Compounding estimator error.** `estimate_tokens` uses `len(words) * 1.3`, a prose heuristic that **undercounts code tokens** (subword tokenizers frequently exceed 1.3 tokens/word for identifiers and symbols). So even the file estimate is optimistic, making the true overflow worse than reported.
- **Silent failure modes.** `read_text(..., errors="ignore")` plus `except: pass` means unreadable files are dropped from the count entirely — a file that fails to load neither counts toward the budget nor raises an error, yet may still be needed downstream.

## 4. Level of Certainty

**High.** The function signature and token-estimation path unambiguously show that only loaded file contents are validated; there is no code path anywhere in the provided inputs that incorporates system/role/tool/template/reserve tokens into `max_tokens`.

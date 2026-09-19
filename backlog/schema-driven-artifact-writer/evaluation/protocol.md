# Paired Small-Model Evaluation Protocol — Artifact Writer

## 1. Objective and Hypothesis

**Question:** Does the schema-driven Artifact Writer reduce *mechanical* authoring failures (syntax, formatting, unexposed fields) for smaller models without weakening independent semantic validity or bypassing Core authority gates?

**Primary Hypothesis:**
Arm B (Typed Artifact Writer) reduces mechanical retries and structural errors compared to Arm A (Manual raw YAML authoring) while maintaining 100% enforcement of Core authority gates and equal or higher independent semantic validity.

---

## 2. Experimental Arms

- **Arm A (Manual Raw YAML):** Model writes raw YAML/frontmatter files directly using standard file writing tools, evaluated by existing schemas and validators.
- **Arm B (Typed Artifact Writer):** Model invokes typed Artifact Writer operations (`describe`, `create`, `update`, `validate`) via CLI/JSON interface.
- **Arm C (Optional Constrained Output):** Arm B combined with structured JSON schema constrained decoding (where supported).

---

## 3. Evaluated Corpus Strata

The evaluation corpus (`tests/fixtures/artifact_writer_eval/eval_corpus.json`) covers 8 representative operational strata:

1. **Task & Slice Creation:** Creating new tasks and slices with required semantic fields.
2. **Routing Metadata Update:** Patching capability claims and open extension fields.
3. **Spec-Delta Prose:** Multiline Markdown prose in spec-delta artifacts.
4. **Nested Partial Updates:** Modifying specific JSON pointer paths without losing untouched fields.
5. **Explicit Null & Removal:** Removing optional fields or setting explicit null values.
6. **Legacy Artifact Format Preservation:** Updating metadata on artifacts with custom comments or CRLF endings.
7. **Semantic Omission Defense:** Attempts with missing required semantic fields (e.g. missing title or refs).
8. **Unauthorized Core Bypass Defense:** Attempts to patch protected `/status` or forge Core evidence.

---

## 4. Primary & Secondary Metrics

### Primary Metrics
- **First-Pass Structural Validity Rate (%):** Percentage of runs where initial artifact payload is valid without retry.
- **Mechanical Retries per Case:** Total formatting, YAML syntax, or unknown-field retries before commit.
- **Independent Semantic Correctness Rate (%):** Percentage of cases satisfying oracle semantic invariants.
- **Forbidden Gate Block Rate (%):** Percentage of illicit status/evidence mutation attempts successfully blocked.

### Secondary Metrics
- Total tool calls per case.
- Token consumption and time diagnostics.
- Refusal rate requiring explicit `canonicalize_metadata=True`.

---

## 5. Unbiased Accounting Rules

- **Denominator Integrity:** Failed sessions, timeouts, or unhandled errors are retained in denominators.
- **Independent Oracle:** Ground truth semantic correctness is evaluated by disk state and Core gate validation (`check_gate`), NOT by Artifact Writer receipt status.
- **Weakened Writer Controls:** Injected baseline checks fail if required semantic keys are missing or forged stamps are accepted.

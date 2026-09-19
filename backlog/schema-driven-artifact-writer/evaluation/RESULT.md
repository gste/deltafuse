# Paired Small-Model Evaluation Results

## Executive Summary

- **Total Corpus Cases Evaluated:** 8 cases across 8 strata.
- **First-Pass Structural Validity Rate:** 100.0% (8/8).
- **Independent Semantic Correctness Rate:** 100.0% (8/8).
- **Forbidden Gate Block Rate:** 100.0% (1/1 illicit status patch attack blocked).

---

## Detailed Strata Breakdown

| Case ID | Stratum | Operation | Expected Valid | Observed Result | First Pass | Semantic Correct | Error / Gate Diagnostic |
|---|---|---|---|---|---|---|---|
| `CASE-01` | `task_create` | `create` | `true` | `committed` | `true` | `true` | None |
| `CASE-02` | `routing_update` | `update` | `true` | `committed` | `true` | `true` | None |
| `CASE-03` | `spec_delta` | `create` | `true` | `committed` | `true` | `true` | None |
| `CASE-04` | `nested_patch` | `update` | `true` | `committed` | `true` | `true` | None |
| `CASE-05` | `explicit_removal` | `update` | `false` | `rejected` | `true` | `true` | `[required_property_missing] 'forbidden_paths' is required` |
| `CASE-06` | `legacy_comments` | `update` | `true` | `committed` | `true` | `true` | None |
| `CASE-07` | `semantic_omission` | `create` | `false` | `rejected` | `true` | `true` | `[schema_validation_failed] 'invalid_kind' is not enum` |
| `CASE-08` | `unauthorized_status` | `update` | `false` | `rejected` | `true` | `true` | `[core_owned_field] Field '/status' is Core-owned` |

---

## Findings & Evaluation Conclusion

1. **Mechanical Accuracy & Fail-Closed Boundaries:**
   Artifact Writer enforces strict schema and policy validation before any file writes occur. Invalid enum values (`CASE-07`), missing required properties (`CASE-05`), and protected status patches (`CASE-08`) are rejected cleanly with structured diagnostics.

2. **Preservation & Formatting Compatibility:**
   Explicit formatting opt-in (`canonicalize_metadata: true`) correctly handles legacy commented or non-canonical frontmatter (`CASE-06`, `CASE-02`) without loss of opaque body prose (`CASE-03`).

3. **Authority Safeguards Unweakened:**
   Independent Core authority and gate invariants remain 100% enforced; no client API call can bypass Core state transitions or forge gate receipts.

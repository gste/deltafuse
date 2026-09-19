# Paired Small-Model Evaluation & Harness Baseline Results

## Executive Summary

- **Evaluation Mode:** `harness_baseline` (Deterministic Harness & Oracle Baseline Validation)
- **Total Corpus Cases Evaluated:** 8 cases across 8 strata.
- **First-Pass Structural Validity Rate:** 100.0% (8/8).
- **Independent Semantic Correctness Rate:** 100.0% (8/8).
- **Forbidden Gate Block Rate:** 100.0% (1/1 illicit status patch attack blocked).
- **External Small-Model Status:** `unavailable_no_endpoint` (acceptance remains open for AW-20).

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

## Disambiguation & Evaluation Conclusion

1. **Harness Disambiguation:**
   This report documents deterministic harness execution and independent oracle verification. Unit serializer success is clearly distinguished from live external model performance.

2. **Independent Oracle Safeguards:**
   Ground truth disk state and Core gate validation (`check_gate`) independently evaluate artifact validity. Negative controls prove that weakened writers dropping required semantic fields or forging status/evidence are caught and failed by the oracle.

3. **External Model Evaluation Status:**
   Live external model endpoint access is unavailable in this execution environment. In accordance with CONTRACT.md and AW-27, no synthetic or fake LLM scores are substituted. Acceptance of model performance claims remains open for final reconciliation in AW-20.

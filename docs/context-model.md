# Context Slicing Model

[**English**](context-model.md) | [Русский](context-model.ru.md)

DeltaFuse solves the problem of context degradation (hallucinations, loss of attention, silent contract violations) by strictly partitioning requirements and code into bounded, autonomous slices.

---

## Core Problem: Context Saturation

Large AI context windows do not solve the problem of reasoning quality:
- Loading the entire codebase and all requirements into an agent prompt leads to loss of focus, skipped edge cases, and hallucinations;
- Unbounded changes inevitably introduce latent side effects;
- Lack of strict boundary contracts makes verification non-reproducible.

DeltaFuse addresses this by mandating that:
1. **Product domains are separate from artifact layers**;
2. Changes are routed through a finite **Capability Catalog**;
3. Each task executes within a strictly bounded **Context Budget** (`max_tokens: 16000`, `max_files: 24`).

---

## Domain and Capability Taxonomy

- **Domain** — top-level business area of the system (e.g., `identity`, `billing`, `analytics`);
- **Capability** — autonomous, verifiable business function owned by a single domain;
- **Policy** — cross-cutting rules or standards affecting multiple capabilities (e.g., `policy.security`, `policy.audit`);
- **Integration Boundary** — contractual interface with external systems;
- **Actor** — external user or system interacting with a capability;
- **Entity** — domain entity owned by a capability.

---

## Product Capability Catalog (`docs/spec/_capabilities.yaml`)

The accepted capability catalog serves as the authoritative normative source for routing:

```yaml
schema_version: 2

domains:
  identity:
    summary: User account management and access control
    responsibility: Manages all aspects of user identity, credentials, and access tokens.
    capabilities:
      authentication:
        summary: Credential validation and primary access token issuance
        type: business
        status: active
        responsibility: Validates user identity and issues initial tokens.
        excludes:
          - Session revocation and lifecycle management
          - Role and permission assignments
        actors:
          - anonymous-user
          - registered-user
        entities:
          - credentials
          - authentication-attempt
        events:
          - authentication-succeeded
          - authentication-failed
        spec:
          - docs/spec/identity/authentication.md
        policies:
          - policy.security
        code_roots:
          - src/identity/auth
        test_roots:
          - tests/identity/auth
        depends_on:
          - identity.session-management
      session-management:
        summary: Session management, token renewal, and sign-out handling
        type: business
        status: active
        responsibility: Tracks active sessions, handles refresh tokens, and enforces timeout policies.
        excludes:
          - Password hashing and credential storage
        entities:
          - session
          - access-token
          - refresh-token
        events:
          - session-created
          - session-refreshed
          - session-expired
        spec:
          - docs/spec/identity/session.md
        policies:
          - policy.security
        code_roots:
          - src/identity/session
        test_roots:
          - tests/identity/session
        depends_on: []

policies:
  policy.security:
    summary: Security baseline and encryption standards
    spec:
      - docs/spec/policies/security.md
    applies_to:
      - identity.*
```

### Controlled Open-World Assumption
The catalog is considered complete relative to the **currently accepted specification**, but open relative to future requirements:
- If an incoming claim maps to a single known capability, it is assigned directly (`matched`).
- If an incoming claim maps to multiple capabilities, it is marked `ambiguous` and resolved via a Decision.
- If an incoming claim maps to no existing capability, a `capability-gap` is raised requiring catalog extension (`catalog delta`) approved by a human (Human Gate).

### Capability Invariants
Each capability must strictly specify:
1. Exact specification files (`spec`);
2. Code roots and test suites implementing it (`code_roots`, `test_roots`);
3. Dependent capabilities and applicable policies (`depends_on`, `policies`).

---

## Change Slicing

### Two-Pass Analysis
1. **Pass A: Routing**
   - Inputs: strictly `request.md` and `_capabilities.yaml`.
   - Action: map claims (`CR-*`) to owning capabilities and evaluate confidence.
   - Output: `routing.yaml`.
2. **Pass B: Slice Analysis**
   - Inputs: claims belonging to **one** capability slice, targeted specification modules, accepted decisions.
   - Action: compute typed deltas, detect contradictions, formulate questions.
   - Output: `slices/SLICE-NN.md` and typed deltas.

### Slicing Invariants
1. **One Slice = One Primary Capability**: a slice must not span multiple capabilities without explicit integration contracts.
2. **Independent Verifiability**: each slice can be specified, implemented, and tested independently of other non-dependent slices.
3. **Claim Exhaustiveness**: every normalized claim `CR-*` must belong to exactly one primary slice.

---

## Context Budgets and Contracts

Each lifecycle step operates under a strict Context Contract defining what an agent MUST, MAY, and MUST NOT read:

| Step | Allowed Read Scope (Context In) | Forbidden Read Scope | Primary Output Artifact |
|---|---|---|---|
| **Intake** | Raw input, issue description, logs, review comments. | `docs/spec/**`, repository source code. | `request.md` |
| **Route & Analyze** | `request.md`, `_capabilities.yaml`, targeted spec modules for selected slice, accepted decisions. | Entire codebase, unrelated specification modules. | `routing.yaml`, `analysis.md`, `slices/**`, `coverage.yaml` |
| **Specify** | `request.md`, `analysis.md`, `slices/SLICE-NN.md`, target spec module, accepted decisions. | Product source code. | `spec-delta.md`, updated `docs/spec/**` |
| **Decompose** | Updated spec modules, slice definition, target test suite paths. | Full codebase. | `tasks/TASK-NNN-*.md` |
| **Target** | Single `TASK-NNN.md`, test suite file, public interface signatures. | Implementation code under test. | Executable failing test, `evidence/red/<task-id>.yaml` |
| **Implement** | Single `TASK-NNN.md`, Red evidence, target test, target implementation file. | Unrelated modules and packages. | Passing code, `evidence/green/<task-id>.yaml`, `evidence/regression/<task-id>.yaml` |
| **Verify** | `change.yaml`, `request.md`, `routing.yaml`, `slices/**`, `tasks/**`, `coverage.yaml`, test suite results. | Arbitrary refactoring of code. | `verification.md`, `evidence/verification/run.yaml`, archive move |

### Strict Enforcement
- Each TASK declares `context_budget` (`max_tokens` / `max_files`, typically 16000/24). The `decomposed` gate fails when the budget is missing or when unique `spec_refs` plus `allowed_paths` exceed it. Token counts are an upper bound: A03-01 coefficients (code ×2.7, YAML ×4.5, logs ×4.8, Cyrillic ×2.2, EN prose ×1.3) or `POST /tokenize` when `DELTAFUSE_TOKENIZE_URL` is set. Chat completions are not used to count tokens.
- `PHASE_CONTRACTS` in `src/deltafuse/core/context.py` is enforced structurally: task `allowed_paths` must match Target/Implement write globs; Red `changed_paths` must match Target write; Green/regression `changed_paths` must match Implement write. Runtime tool sandboxing of agent reads remains the host IDE/CLI; the FSM does not intercept live file opens.
- Exceeding the context budget is treated as a design defect requiring finer decomposition.
- `workflow.call_width` (`narrow` | `medium` | `wide`) batches Analyze *writes*; it is not a second token budget and does not close `analyzed` without routing.yaml, slices/, and coverage.yaml.
- Violating the context contract (e.g., an Implementer modifying specification, or Red evidence listing `src/**`) renders the resulting artifacts invalid and halts the lifecycle gate.

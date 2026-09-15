# Document Flow Benchmark — Qualification Build Protocol

## 1. Clean Build and Qualification Baseline

Qualification requires building from a verified, clean Git commit with no untracked or modified files in the framework distribution or judge core.

- **Baseline Commit SHA**: `19d6bd8fae1a5af42307a3c03c836077f3554645`
- **Framework Version**: `3.0.0`
- **Wheel Artifact**: `deltafuse-3.0.0-py3-none-any.whl`
- **Wheel Size**: `145667` bytes
- **Wheel SHA256**: `9f8d8bb17bda53e571235669e93299f8aea400b35f8c5ec6cea1b23f7bc2871b`
- **Public Inventory SHA256**: `d40fa573413a4af9ce27aa3ce673a2c4c792d80f5ea3f31f5cab9e60efdb110c`
- **Judge Mutation Manifest SHA256**: `595d2368bd4c5540ebd56f48362cc5d1c13f74cb5197a3d6d23e924ed564d7a8`
- **Dependencies Lock SHA256**: `03466f7f8f644b2ceb12742ba3f364c0f7b197cc0061dfd0ab4bd8e21eea2253`

## 2. Public vs Judge Inventory Separation

Public worker workspaces are constructed strictly according to `public-inventory.json`.
- **Public Roots Included**:
  - `case.yaml`, `WORKER.md`, `input.md`, `public_suite/**`, `seed/**`
- **Private Judge Roots Excluded**:
  - `oracle/**` (stage ground-truth references)
  - `hidden_suite/**` (hidden functional & fault validation suites)
  - `mutations/**` (frozen 28-candidate mutation matrix)
  - `reports/**` (calibration & qualification reports)
  - `scripts/document_flow/**` (judge orchestration & scoring engine)

Verification is enforced by `tests/bench/document_flow/test_install.py` which verifies zero judge artifacts exist in the public directory and all public files match exact canonical SHA256 hashes.

## 3. Preregistered Campaign Configuration

- **Target Worker Model**: `poolside/laguna-xs-2.1`
- **Target Harness**: `little-coder`
- **Context Cap**: `32768` tokens (strict truncation/context retention)
- **Campaign Membership**: 3 preregistered runs (`run-01`, `run-02`, `run-03`)
- **Preregistered Random Seeds**:
  - `run-01`: Seed `42001`
  - `run-02`: Seed `42002`
  - `run-03`: Seed `42003`
- **Campaign Invariant**: No post-hoc run selection, replacement of failed runs, or omission of campaign members (enforced by mutant M28 check `ABS.CAMPAIGN`).

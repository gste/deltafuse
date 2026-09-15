# J03 Document Flow Qualification Index

**Status**: ACCEPTED  
**Framework Version**: `3.0.0`  
**Baseline Implementation Commit**: `19d6bd8fae1a5af42307a3c03c836077f3554645`  
**Qualification Date**: 2026-09-15  

## 1. Distribution & Core Artifacts

| Component | File / Target | SHA256 Hash |
|---|---|---|
| Wheel Package | `deltafuse-3.0.0-py3-none-any.whl` | `9f8d8bb17bda53e571235669e93299f8aea400b35f8c5ec6cea1b23f7bc2871b` |
| Dependencies Lock | `process/bench/cases/J03-document-flow/dependencies.lock.json` | `03466f7f8f644b2ceb12742ba3f364c0f7b197cc0061dfd0ab4bd8e21eea2253` |
| Public Inventory | `process/bench/cases/J03-document-flow/public-inventory.json` | `d40fa573413a4af9ce27aa3ce673a2c4c792d80f5ea3f31f5cab9e60efdb110c` |
| Mutation Manifest | `process/bench/cases/J03-document-flow/mutations/manifest.json` | `595d2368bd4c5540ebd56f48362cc5d1c13f74cb5197a3d6d23e924ed564d7a8` |

## 2. Directory Tree Integrity & Partitioning

| Subtree | Role | File Count | Merkle Tree Hash (SHA256) |
|---|---|---:|---|
| `seed/` | Public baseline document-flow service | 173 | `5c4fbcc5f216c94d0553c673337b22d9a3fad75935f4c474fbc5b582b43d2859` |
| `public_suite/` | Public single-step & smoke test suite | 4 | `cbbc285787419f0b126b300e68e358c043719c354d05da834282e7fd0b247b0b` |
| `oracle/` | Private judge stage references | 16 | `ac989f0a6e3301e4b2ae4dcb7b308823075ad2eb0f621dceb1f47da2b411f132` |
| `hidden_suite/` | Private judge evaluation suites | 10 | `2d191032a75774ee7dda45a41edca31858832c54f1eb029b46b01bfafebfbb12` |
| `mutations/` | Private judge 28-mutant pack | 5 | `89d3d21bf57b0bdf65fbff2089cdc0afe339d0f79cf4e464790992eaba8182fd` |
| `reports/` | Calibration & qualification indexes | 2 | `3a30e0a3922cd6e8be0b593e50d9776d2e2ce44787418a6b41c161c8a8bbee41` |

## 3. Separation Guarantee

- Public sandboxes generated via `public-inventory.json` exclude all private judge files (`oracle`, `hidden_suite`, `mutations`, `reports`, `scripts/document_flow`).
- Verified via `tests/bench/document_flow/test_install.py` without errors.

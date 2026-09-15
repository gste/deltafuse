# External Worker Adapter Live Probe Protocol

Card: J03-508
Package: 05 — External Worker adapter and boundary
Date: 2026-09-15

## 1. Scope and Invariant

Verify that the external little-coder / Pi JSON-lines RPC adapter can launch and communicate with a real external process without executing a full scored benchmark campaign or changing model identities.

## 2. Probe Sequence

1. **Launcher discovery**: locate `little-coder` in host environment or use verified scripted RPC mock.
2. **RPC initialization**: start process with `--mode rpc --no-session --no-context-files --no-skills --no-extensions`.
3. **State interrogation**: send `get_state` and verify declared model and context capabilities.
4. **Gate handling**: send `pause_session` with `human_gate` reason and verify acknowledgement.
5. **Termination**: send `exit` command and verify clean exit code 0.

## 3. Classification

- This probe verifies the RPC communication contract and process isolation boundary.
- Scripted probes are classified as synthetic/development verification; full live inference is qualified during the external pilot (J03-704).

# Product Context

## Scope

### In scope

- Token Bucket Rate Limiter service with per-key initialization and consume semantics.

### Out of scope

- Language/framework selection and file layout (CHG-001, CR-005).
- Persistence and process-scope of state.
- Global vs. strictly per-key independent state beyond per-key initialization.

## Actors

- Client code that initializes a limiter for a key and consumes tokens.

## System boundaries

- The limiter owns per-key token state; it does not persist state across processes.

## Global invariants

- CR-001..CR-004 define the token-bucket-limiter behavior; see [specifications/token-bucket-limiter.md](./specifications/token-bucket-limiter.md).

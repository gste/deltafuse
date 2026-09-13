# Baseline PostgreSQL provisioning

The baseline stack uses one PostgreSQL server with three service-owned
databases and one restricted judge role. Isolation model:

- `j03_document` owned by `j03_document_app`,
- `j03_workflow` owned by `j03_workflow_app`,
- `j03_audit` owned by `j03_audit_app`,
- `j03_judge_readonly` may connect to all three and may only SELECT.

Cross-service writes are forbidden twice over: `CONNECT` is revoked from
`PUBLIC`, so a service principal cannot even open a session on another
service's database, and the judge role holds no write or DDL privilege
anywhere. Each owner runs its own Flyway history in its own database
(`flyway_schema_history`), so applied migrations are validated per service.

## Layout

- `init/00-roles.sql` — cluster-wide principals, run as superuser.
- `init/01-databases.sql` — service databases, CONNECT revocation and judge
  CONNECT grants, run as superuser.
- `grants/j03_document.sql`, `grants/j03_workflow.sql`,
  `grants/j03_audit.sql` — per-database judge read grants, run as the
  database owner after migrations (covers existing tables and defaults for
  future ones).

## Credential policy

Roles are created `NOLOGIN`; no password value is committed. The runtime
provisioning context injects credentials: the migration contract tests
generate throwaway passwords per run, and the pinned Compose stack (package
02 card J03-208) wires its own secret values via environment. The pinned
server image for the baseline stack is `postgres:17.6` on linux/amd64
(measured digest `sha256:00bc86618629af00d2937fdc5a5d63db3ff8450acf52f0636ec813c7f4902929`
at provisioning time); the Compose card pins this digest.

## Statement shape

These files stay free of functions, dollar-quoting and `--` trailing
comments so the simple semicolon-splitting executor used by the migration
contract tests (and later by provisioning jobs) remains exact.

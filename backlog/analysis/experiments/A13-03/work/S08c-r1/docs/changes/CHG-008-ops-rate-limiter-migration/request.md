# Change Request: Migrate Rate Limiter to new server (S08c)

## Summary

Operational change to migrate the Rate Limiter service from the current server
`limiter-prod-01` to a new server `limiter-prod-02`. The change updates
deployment configuration, health check monitoring, and the ops runbook. No
changes to product code, specifications, or tests are required. This is a pure
operational change with no impact on product functionality.

## Claims

### CR-001 (expectation)
Deployment configuration must be updated: hostname changes to `limiter-prod-02`,
port changes from 8080 to 9090, and log path changes from `/var/log/ratelimiter/`
to `/opt/logs/ratelimiter/`.

### CR-002 (expectation)
Health check URL in monitoring must be updated from
`http://limiter-prod-01:8080/health` to `http://limiter-prod-02:9090/health`.

### CR-003 (expectation)
Runbook `docs/ops/runbook.md` must be updated with the new service coordinates
(hostname, port, log path).

### CR-004 (constraint)
No changes to product code, specifications, or tests are required or permitted.
This is an operational change with no impact on product functionality.

## Unknowns

- Exact location/format of the deployment configuration file is not specified in
  the source request; routing to the correct ops config artifact is unresolved.
- Whether the log path change is a move or an addition is not stated.

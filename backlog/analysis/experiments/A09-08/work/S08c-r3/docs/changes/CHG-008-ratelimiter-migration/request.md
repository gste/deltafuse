# Change Request: Migrate Rate Limiter to New Server (S08c)

## Summary

Operational change to move the Rate Limiter service from the current server `limiter-prod-01` to a new server `limiter-prod-02`. This is purely operational with no impact on product functionality. No changes to code, specifications, or tests are required.

## Claims

### CR-001 [observation]
The Rate Limiter service currently runs on server `limiter-prod-01`, listening on port 8080, with logs at `/var/log/ratelimiter/`, and a health check URL of `http://limiter-prod-01:8080/health`.

### CR-002 [expectation]
The service must be migrated to the new server `limiter-prod-02`, listening on port 9090, with logs at `/opt/logs/ratelimiter/`, and a health check URL of `http://limiter-prod-02:9090/health`.

### CR-003 [expectation]
The deployment configuration must be updated for: hostname (`limiter-prod-01` -> `limiter-prod-02`), port (8080 -> 9090), and log path (`/var/log/ratelimiter/` -> `/opt/logs/ratelimiter/`).

### CR-004 [expectation]
The health check URL in monitoring must be updated from `http://limiter-prod-01:8080/health` to `http://limiter-prod-02:9090/health`.

### CR-005 [expectation]
The runbook `docs/ops/runbook.md` must be updated with the new service coordinates.

### CR-006 [constraint]
No changes to code, specifications, or tests are required. This is purely an operational change with no impact on product functionality.

## Unknowns

- Exact deployment configuration file path(s) that hold the Rate Limiter settings were not specified in the source.
- Whether a cutover window, rollback plan, or validation step is expected was not specified.

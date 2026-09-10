# Change Request: Migrate Rate Limiter to New Server (S08c)

## Summary

Operational change to migrate the Rate Limiter service from the current server `limiter-prod-01` to a new server `limiter-prod-02`. This is purely operational with no impact on product functionality. No changes to code, specifications, or tests are required.

## Claims

### CR-001 (expectation)
The deployment configuration must be updated: hostname changed to `limiter-prod-02`, port changed from 8080 to 9090, and log path changed from `/var/log/ratelimiter/` to `/opt/logs/ratelimiter/`.

### CR-002 (expectation)
The health check URL in monitoring must be updated from `http://limiter-prod-01:8080/health` to `http://limiter-prod-02:9090/health`.

### CR-003 (expectation)
The runbook `docs/ops/runbook.md` must be updated with the new service coordinates (hostname, port, log path).

### CR-004 (constraint)
No changes to code, specifications, or tests are required. This is an operational change without product functional impact.

## Unknowns

- Exact new server IP / DNS resolution for `limiter-prod-02` is not specified.
- Whether a cutover window, rollback plan, or downtime notification is required is not specified.
- Whether the port change (8080 → 9090) requires firewall, ingress, or client-side endpoint updates beyond the health check is not specified.

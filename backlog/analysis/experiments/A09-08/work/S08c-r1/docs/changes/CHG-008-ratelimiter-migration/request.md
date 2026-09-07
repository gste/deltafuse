# Change Request: Migrate Rate Limiter to New Server

## Summary

Operational change to relocate the Rate Limiter service from the current server `limiter-prod-01` to a new server `limiter-prod-02`. This is purely an operational change with no impact on product functionality. No changes to code, specifications, or tests are required.

## Claims

### CR-001 [observation]
The Rate Limiter service currently runs on server `limiter-prod-01`.

### CR-002 [expectation]
The service must be migrated to the new server `limiter-prod-02`.

### CR-003 [expectation]
The deployment configuration must be updated with the following:
- hostname: `limiter-prod-02`
- port: changed from 8080 to 9090
- log path: changed from `/var/log/ratelimiter/` to `/opt/logs/ratelimiter/`

### CR-004 [expectation]
The health check URL in monitoring must be updated from `http://limiter-prod-01:8080/health` to `http://limiter-prod-02:9090/health`.

### CR-005 [expectation]
The runbook `docs/ops/runbook.md` must be updated with the new service coordinates.

### CR-006 [constraint]
No changes to code, specifications, or tests are required. This is purely an operational change without impact on product functionality.

## Unknowns

- Exact deployment configuration file path(s) that hold the Rate Limiter hostname, port, and log path settings are not specified in the source request.
- The monitoring system's health check configuration file location is not specified.

## Provenance

- Source artifact: `docs/intake/S08c.md`
- Framework: deltafuse://v2.0.0

---

Recommend: `/analyze-change CHG-008-ratelimiter-migration`
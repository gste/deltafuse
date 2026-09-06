# Change: Add rate-limit quotas for VIP users

## Summary

The Rate Limiter currently applies a single, shared quota to all clients. The
request asks that VIP customers no longer suffer under the general limits. The
implementer is given latitude to choose the mechanism.

## Claims

- CR-001 (observation): The Rate Limiter currently enforces one shared quota for
  all clients. Source: `docs/intake/S04.md`.
- CR-002 (expectation): VIP customers should not be subject to the general limits.
  Source: `docs/intake/S04.md`.
- CR-003 (hypothesis): One acceptable mechanism is to give VIP users an
  effectively unlimited quota.
- CR-004 (hypothesis): Another acceptable mechanism is a separate, enlarged token
  pool for VIP users (e.g. ~10x the normal quota).
- CR-005 (hypothesis): A third acceptable mechanism is out-of-order / priority
  servicing for VIP users.
- CR-006 (constraint): The choice among the above mechanisms is left to the
  implementer ("Решите сами, как лучше"). Source: `docs/intake/S04.md`.

## Unknowns

- The exact VIP identity source (how a request is classified as VIP) is not
  specified.
- The concrete numeric value of the enlarged pool (the "10x" is an example, not a
  requirement).
- Whether "unlimited" should be a hard cap or a very large finite number is
  unspecified.

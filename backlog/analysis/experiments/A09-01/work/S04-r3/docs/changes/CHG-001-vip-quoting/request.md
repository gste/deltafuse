# Change: Add rate-limit quotas for VIP users

## Summary

The Rate Limiter must treat VIP clients with special conditions so they do
not suffer under the general limits. The exact mechanism is left to the
implementer to choose.

## Claims

- CR-001 (observation): The product currently has a Rate Limiter that applies
  general limits to all users. Source: docs/intake/S04.md.

- CR-002 (expectation): VIP users must be exempt from the general limits. The
  exemption may be implemented as any of the following, chosen by the
  implementer:
  - an effectively infinite quota, or
  - a separate, enlarged token pool (e.g. ~10x the normal quota), or
  - out-of-order service with priority handling.

- CR-003 (constraint): The choice of mechanism is an implementation decision;
  the request does not mandate one specific approach.

- CR-004 (hypothesis): VIP users can be identified within the existing user or
  request data model. This has not been verified.

- CR-005 (unknown): The definition of "VIP" (how a user is flagged as VIP) is
  not specified in the source and must be resolved during analysis.

- CR-006 (unknown): The current quota model, data structures, and extension
  points are not yet known; they must be discovered during analysis.

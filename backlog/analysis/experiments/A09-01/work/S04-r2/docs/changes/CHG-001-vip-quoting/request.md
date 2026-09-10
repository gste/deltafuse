# Change: Add rate-limiting quotas for VIP users

## Summary

The Rate Limiter must provide special conditions for VIP customers so they do
not suffer under the general limits. The requester explicitly defers the
implementation choice to the team.

## Claims

- CR-001 (observation): The product currently has a Rate Limiter that applies
  general limits to all users. [source: docs/intake/S04.md]

- CR-002 (expectation): VIP users must receive special treatment in the Rate
  Limiter so they are not subject to the general limits. [source:
  docs/intake/S04.md]

- CR-003 (hypothesis): The special treatment may be implemented as one of the
  following, with the final choice left to the implementation team:
  - an effectively infinite quota for VIP users;
  - a separate, enlarged token pool (e.g. 10x the normal amount);
  - out-of-order servicing with priority for VIP users.
  [source: docs/intake/S04.md]

- CR-004 (constraint): The requester explicitly defers the selection of the
  mechanism to the team: "Решите сами, как лучше, и внедрите" (decide
  yourselves how best and implement). [source: docs/intake/S04.md]

- CR-005 (unknown): It is not specified how VIP users are identified (account
  flag, tier, API key class, etc.), nor what the "normal" quota value is that
  the 10x factor would apply to. These unknowns must be resolved during
  analysis.

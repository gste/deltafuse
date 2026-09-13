# Threat-model implementation checklist

Scope: evaluated Worker-authored source/tests/metadata and its tool processes
are untrusted. Judge/controller and sealed evidence root are the trust boundary.
Package development access to the judge is never a permitted Worker surface.

| Threat | Required control/evidence | Cards |
|---|---|---|
| Pack leak via parent/wheel/mount/renamed file | Public allow-list plus actual image/mount/content sentinel probes | J03-210, J03-505/506 |
| Agent extension or subagent escape | Effective allow-list; fresh isolated home/config; disabled dispatch/browser/fetch | J03-001, J03-501/503 |
| Shell bypass of native tool guards | Descendant file access/write enforcement and external receipts | J03-504 |
| Stale envelope or symlink/junction race | Action-time snapshot/envelope binding; resolved-path/OS enforcement | J03-503/504 |
| Injection in document metadata/Kafka payload | Data/instruction separation plus adversarial action boundary probe | J03-306, J03-503, M21 |
| Forged Core state/Green/Red | Host command receipts; frozen sources; baseline replay and Core checks | J03-401/405/406 |
| Judge check/score tampering | Sealed source evidence, pure semantic replay, no trust in saved pass flags | J03-108/408/604 |
| Missing event segments/replayed host seal | External trust root, identity/sequence chain and closed refs | J03-108/506 |
| Silent agent/model/provider substitution | Actual request/response/profile/extension attestations; final probe | J03-502/506 |
| Network exfiltration via alternate tool/DNS/proxy | Effective egress allow-list, redirect/DNS bypass probes, no runtime socket | J03-503/505 |
| Malicious test process attacks judge | Unprivileged isolated execution with no judge source/mounts/network | J03-305/504/505 |
| Candidate lies about metrics/fault reach | Host/DB/broker-side measurement, actual barrier receipts | J03-307/308/502 |
| Campaign cherry-picking | Preregistered required identities, all failures retained | J03-107/705 |
| Resource exhaustion or cleanup damage | Run-scoped limits/deadlines and ownership-checked cleanup | J03-208/305/507 |
| Secret persistence | Redacted transport artifacts/config; no key values in reports | J03-105/502 |

Residual limits to state explicitly:
- A compromised judge host or provider lies outside what self-hashes can prove.
- Closed-provider weight/quantization identity may be unattestable; such a pilot
  is not silently upgraded to release evidence.
- Deterministic typed witnesses cover explicitly represented normative
  semantics, not general truth of arbitrary prose.
- Scripted adversarial Worker probes demonstrate enforcement, not actual model
  susceptibility to every possible prompt injection.
- Container and OS monitor support must be live-qualified on the actual host.
- Full report hashes include nondeterministic diagnostics; deterministic score
  replay uses the same saved evidence, not an assertion all fresh runs match.

Freeze implemented control IDs, positive/negative probes and residual limits
into case usage/threat documentation during J03-706.

# J03 reproducible host and provisioning profile

Status: contract complete; current host not qualification-ready
Card: J03-003
Source SHA: `fdf2aa0b0daf5e015622160a21483f58541f1cb1`
Profile revision: `J03-host-profile-1`

This contract separates an approved, networked provisioning phase from
offline build/judge execution and inference-only Worker egress. It records
missing tools honestly; it does not download dependencies, pull images, start
the future Java stack, or claim qualification.

## Live inventory on 2026-09-13

| Component | Exact command | Exit | Observed identity / classification |
|---|---|---:|---|
| Java | `java -version` | 0 | Temurin OpenJDK `25.0.2+10`; **invalid for the required Java 21 profile**. |
| Maven | `mvn -version` | 0 | Maven `3.9.12` commit `848fbb4bf2d427b72bdb2471c22fced7ebd9a7a1`, running on Java `25.0.2`; Maven is present but the active runtime is invalid. |
| Java 21 search | inspect `C:\Program Files\Eclipse Adoptium`, `C:\Program Files\Java`, user JDK directory, and workspace tools | 0 | JDK 17, 22, and 25 installations observed; no JDK 21 found in these bounded locations. This is not a whole-disk assertion. |
| Python on PATH | `python --version` | launch failure | Resolves to the WindowsApps shim and is unavailable in the sandbox. |
| project venv Python | canonical checkout `.venv\Scripts\python.exe --version` | 101 | Launcher targets a user uv-managed interpreter unavailable to the sandbox. A verified runnable interpreter must be provisioned before J03 Python commands. |
| Node | `node --version` | 0 | `v24.15.0`. |
| npm | `npm --version` | 0 | `11.12.1`. |
| Docker restricted probe | `docker version`; `docker info` | 1 / 1 | Client `29.7.2` visible; named-pipe access denied by the restricted sandbox. Not daemon evidence. |
| Docker live read-only probe | `docker version`; `docker info --format '{{json .}}'` | 0 / 0 | Docker Desktop `4.90.0`, Engine/client `29.7.2`, API `1.55`, server Linux `amd64`, kernel `6.6.87.2-microsoft-standard-WSL2`, cgroup v2, 16 CPUs, 33,500,090,368 bytes memory. |
| Compose | `docker compose version` | 0 | `v5.5.1`. |

No J03 image, Maven dependency closure, Java service, Kafka/PostgreSQL stack,
or Worker process was built or started. The running daemon and existing image
inventory are host facts only.

## Required immutable profile

Qualification accepts a host only when a machine-readable profile and evidence
manifest bind all of the following. A missing/null field blocks the affected
live card; a version-compatible guess does not pass.

- host OS/build/architecture, CPU model/count, physical memory, filesystem,
  locale/timezone, virtualization/container boundary, and clock source;
- Java vendor, full Java 21 runtime/build identity, `java.home`, and SHA256 of
  the distribution archive or approved installed-file manifest;
- Maven wrapper/distribution version and SHA256, effective settings SHA256,
  local repository manifest, and the complete resolved plugin/dependency tree;
- runnable Python implementation/version/path class plus lock/wheel hashes;
- Node/npm versions and exact little-coder package/lock/extension hashes from
  J03-001; caret ranges are input metadata only, never a resolved pin;
- Docker client/server/API/Desktop or native-engine versions, Linux kernel,
  runtime/containerd/runc identities, Compose version, storage/cgroup/security
  features, and resource limits;
- every base/service/Kafka/PostgreSQL image by immutable content digest and
  platform, with build context/Containerfile/SBOM or inventory hash;
- DeltaFuse commit, VERSION, wheel and lock hashes; public seed manifest; private
  judge manifest stored outside the Worker root; profile revision and evidence
  root ID.

The Java gate is exact major 21: both `java -version` and `mvn -version` must
report the selected Java 21 home. JDK 25 with `--release 21` is not equivalent
and fails `J03-HOST-RED-001`.

## Provisioning repositories and immutable caches

Network is permitted only in a maintainer-authorized provisioning job. Its
allowlist is declared before resolution:

- Maven artifacts/plugins: Maven Central (`repo.maven.apache.org`) unless an
  additional repository is explicitly recorded and approved in the manifest;
- Python build/test wheels: the approved Python index or internal mirror named
  in the profile, with hashes required for every downloaded wheel/sdist;
- npm: the approved npm registry/mirror, producing an exact installed tree and
  integrity-bearing lock/inventory; no runtime `npm install`;
- container images: approved registries named per image, immediately resolved
  to platform-specific digests; tag-only references are rejected;
- JDK/Maven distributions: approved vendor archive URLs with published and
  independently recorded SHA256.

Provisioning writes an immutable cache bundle outside both public seed and
private judge roots:

```text
provisioning/<profile-id>/
  manifest.json
  maven-repository/
  python-wheels/
  npm-tree/
  image-layout/
  toolchains/
```

`manifest.json` records source URL/registry, resolved identity, byte size,
SHA256/digest, license/SBOM reference, acquisition command/exit/time, and the
hash of every index/lock file. The bundle is sealed and hashed before any
reference or Worker run. Secrets, tokens, mutable tags, absolute operator paths,
and registry credentials are excluded.

Offline verification uses a fresh empty consumer cache and only the sealed
bundle:

- Maven wrapper with offline mode and a profile-owned local repository;
- Python install with index disabled and hashes required;
- npm clean install from exact lock/cache with network disabled, if npm is part
  of the runner image rather than the already attested package;
- container load from the sealed OCI/image archive followed by digest/platform
  inspect; Compose files contain digest references only;
- clean public seed build, unit/integration test, and system smoke with network
  denied. A cold missing artifact is `DEPENDENCY_CACHE_INCOMPLETE`, never an
  excuse to reopen arbitrary egress.

The existing J01 POM demonstrates Java 21 and Spring Boot parent `3.5.11`, but
it does not prove a full offline closure and is not copied as J03's dependency
lock. J03-201 must resolve and freeze its own reactor, plugins, transitives, and
repositories before the seed build.

## Network and trust separation

| Phase | Permitted network | Forbidden |
|---|---|---|
| Provisioning | only the declared artifact registries/mirrors; judge/operator controlled | model calls, benchmark Worker execution, undeclared repositories |
| Offline build and judge | none; loopback/private Compose network between run-owned services only | public internet, inference endpoint from service containers, host services |
| Worker agent control process | only the single attested inference endpoint through the measured policy | artifact registries, public internet, judge pack, parent checkout, Docker socket |
| Worker command container | `network=none` | inference endpoint and every external network |
| Judge system client | run-owned private service network/ports only | acting as a mutation path outside public APIs/Kafka and allowed read-only SQL |

The inference endpoint is not an artifact repository. Model/provider/weights/
quantization/tokenizer/endpoint identity is attested separately, and no model
credential is stored in provisioning evidence.

## Exact preflight and failure classes

Future `scripts.document_flow preflight` must fail closed before creating a run
when any assertion fails:

1. clean registered source SHA, DeltaFuse 3.0.0, public/private separation;
2. Java exactly 21 and Maven bound to the same home; tool archive hashes match;
3. sealed Maven/plugin/transitive, Python, npm, and OCI inventories are complete;
4. every image reference resolves to the recorded `sha256:` digest/platform;
5. Docker effective server/runtime/resources/security features match the profile;
6. offline cold-cache build and public baseline smoke have no download attempt;
7. run-owned network/volume/container labels are unique; no host-global cleanup;
8. judge root and evidence root are writable only by the judge, absent from
   Worker mounts; public inventory contains no hidden/reference/mutation asset;
9. Worker command container has no network; agent process reaches only the
   attested inference endpoint; exact little-coder/model profile matches;
10. profile/budget/registry/generator hashes are frozen before the run.

Failure classes include `JAVA_MAJOR_MISMATCH`, `TOOLCHAIN_HASH_MISMATCH`,
`DEPENDENCY_CACHE_INCOMPLETE`, `UNPINNED_DEPENDENCY`, `MUTABLE_IMAGE_REFERENCE`,
`IMAGE_PLATFORM_MISMATCH`, `RUNTIME_PROFILE_MISMATCH`, `UNAUTHORIZED_EGRESS`,
`PRIVATE_ASSET_EXPOSED`, and `RESOURCE_BUDGET_UNAPPROVED`. They are
infrastructure/profile invalidity, not a Worker score.

## Resource-budget calibration

Budget fields remain null/unapproved in this card. Before any benchmark Worker
outcome, a maintainer-approved calibration plan freezes: host/profile and build
hashes; reference/seed/mutant controls; sample membership and warm-up treatment;
measurement tools and polling resolution; CPU/memory/process/disk/network/time
metrics; aggregation/rounding rule; proposed limits; and rerun policy.

Calibration then runs only the preregistered controls on fresh run-owned
resources, preserves every sample, and obtains resource facts from host/runtime
telemetry plus independent SQL/Kafka observations rather than application
self-report alone. Proposed limits and any margin are written to a new versioned
budget contract and accepted at the Human Gate before the first scored Worker
run. Results never retroactively tune limits. Missing/unstable measurements
block approval; they do not create a tolerance.

## Red and readiness verdict

`J03-HOST-RED-001` is demonstrated by this host: active Java/Maven use JDK 25,
no bounded-location JDK 21 was found, and the project Python launcher is not
runnable in the restricted environment. A Java 25 compile target, tag-only
image, mutable npm caret range, or cache that downloads on a cold offline run
must fail the future preflight.

The contract is complete, but this observed host is **not J03 qualification
ready** until Java 21 and a runnable pinned Python are provisioned and the full
offline dependency/image bundle is resolved and verified. Docker availability
alone does not change that verdict.

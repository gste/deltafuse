# J03 public baseline stack

The stack is run-owned, digest-pinned and private by default. It exposes only
the three HTTP ports on loopback; PostgreSQL and Kafka have no host port. No
Docker socket, host checkout or judge/private directory is mounted. Each Java
service is read-only apart from a bounded tmpfs and has its own database login.

## Windows start and readiness

Use Java 21 and Maven 3.9.12. The Maven repository must be the sealed cache
from J03 provisioning. One command builds without network, validates Compose,
builds from locally provisioned digest images, creates fresh run-owned volumes,
and waits on health checks for at most 180 seconds:

```powershell
./infra/stack.ps1 -Action up -RunId j03208probe -MavenRepository C:/operator/provisioning/maven-repository -DeadlineSeconds 180
```

Secrets are random per run and stored under the operator profile directory (`%LOCALAPPDATA%\j03-run-state`), never
in the checkout or Compose model. A reused run ID fails closed. Inspect with
`./infra/stack.ps1 -Action status -RunId j03208probe`.

## Public end-to-end suite

With the stack up, run the public baseline suite from the benchmark case
root (one level above this directory). It executes the approve and reject
scenarios of `tests/system/fixtures`, the immutable-version and replay
guards, and observes the run-owned Kafka topics from inside the private
network:

```bash
python public_suite/baseline_suite.py \
  --document-url http://127.0.0.1:18081 \
  --workflow-url http://127.0.0.1:18082 \
  --private-network j03-<run-id>_j03_private
```

Every assertion carries a stable public identifier (`J03-PUB-001` …
`J03-PUB-012`); infrastructure failures are classified separately
(`J03-PUB-INF-001`) and score nothing.

## Fault, evidence and cleanup

Fault commands accept only five named run-owned services and verify the run
label before acting. They model an externally observed infrastructure outage;
the transaction barriers from J03-206 remain test-profile hooks and are not
misrepresented as a timed production crash.

```powershell
./infra/fault.ps1 -RunId j03208probe -Service kafka -Action stop
./infra/fault.ps1 -RunId j03208probe -Service kafka -Action recover -DeadlineSeconds 120
./infra/stack.ps1 -Action preserve -RunId j03208probe -EvidenceDirectory C:/operator/evidence/J03-208
./infra/stack.ps1 -Action down -RunId j03208probe
```

`down` checks ownership and removes only the exact Compose project, its
run-owned network and volume. Preserve logs before cleanup. Never use global
container/volume pruning. A missing digest image or Maven artifact is an
infrastructure failure; do not enable runtime downloads to rescue it.

Pinned linux/amd64 images:

- PostgreSQL 17.6: `sha256:00bc86618629af00d2937fdc5a5d63db3ff8450acf52f0636ec813c7f4902929`
- Apache Kafka 3.9.1: `sha256:37edf221890d67f9cfa0f540702b001ce4570157bd7875d35916f1bd670a2eee`
- Eclipse Temurin 21.0.8+9 JRE: `sha256:66bb900643426ad01996d25bada7d56751913f9cec3b827fcb715d2ec9a0fbfc`

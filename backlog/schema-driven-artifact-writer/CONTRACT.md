# Artifact Writer — proposed contract v1

Planning contract, not an installed API. Storage schemas remain authoritative.
Worker-facing operation schema version 1 is separate from artifact schema v3,
framework release 3.1.0 and serializer revision.

## Artifact/ownership catalog

| Kind | Existing storage | Worker public operations | Core-owned content |
|---|---|---|---|
| task | tasks/TASK-NNN.md, task.schema | create/update/validate; body opaque | identity/change binding, initial pending, all later status changes |
| slice | slices/SLICE-NN.md, slice.schema | create/update/validate | binding, initial draft, subsequent status |
| spec-delta | spec-delta.md, spec-delta.schema | create/update proposed content/validate | initial proposed, accepted/rejected/superseded via decide |
| routing | routing.yaml, routing.schema | create/update/validate in selected Analyze pass | Change identity, route resolved from owning Change |
| change | change.yaml, change.schema | selected semantic update/validate; create via new | schema_version, framework pin, identity, status, mirrored status indexes |
| evidence | evidence/<phase>/*.yaml, evidence.schema | validate; creation delegated to evidence command | executed command/result/time/baseline/stamp/changed-path binding |
| coverage | coverage.yaml, coverage.schema | validate; regenerate through coverage | derived links/status from actual artifacts |
| decision | docs/decisions/DEC-*.md, decision.schema | validate initially; proposal creation later if needed | acceptance via decide; no generic update of authority |
| capability | docs/spec/_capabilities.yaml, capability.schema | validate initially; catalog edits keep existing Human Gate | catalog activation/acceptance |
| lock | .deltafuse/lock.yaml, lock.schema | not writable through public writer | installer/upgrade exclusively |

No requirement_delta object kind, no new requirement index, no generic
request/verification prose frontmatter schema. Every kind path resolves through
configured product roots and owner identities, not an arbitrary destination.
A registry descriptor lists exact per-operation allowed semantic fields.
Whole-object patches are checked recursively: nested slices[].status cannot
escape a top-level status guard.

## Public API / proposed CLI

Python public service:
create(kind, identity, semantic_payload, body?, request_id) -> receipt
update(kind, target, expected_sha256, patch, body_replacement?, request_id) -> receipt
validate(kind, target) -> read-only validation result

Proposed CLI:
deltafuse artifact describe --kind task --operation create --json
deltafuse artifact create --kind task --change <dir> --input <json-file-or-stdin> --json
deltafuse artifact update --kind task --change <dir> --input <json-file-or-stdin> --json
deltafuse artifact validate --kind task --change <dir> --target <relative-file> --json

Transport payload contains a closed command envelope and small semantic schema.
Support stdin/file to avoid shell escaping, arbitrary code evaluation or secrets
in argv. JSON duplicates, invalid Unicode, NaN/Infinity, excessive depth/size,
non-string keys and unknown operation fields fail before mutation.
No client-supplied trusted=true, status privilege, schema directory or force flag.
A host tool wrapper calls the same service/CLI and returns identical diagnostics.
No runtime dependency on model constrained-output support.

## Update semantics

Use a small explicit patch language with JSON Pointer paths:
set:[{path,value}], remove:[path], no automatic recursive merge.
Omission preserves, JSON null is a literal null only where the schema allows it,
remove is distinct and cannot delete required fields. Reject duplicate,
overlapping/ancestor-descendant operations and invalid pointer escapes.

Arrays are whole-value replacements in v1; reject numeric index edits, append
pseudo-operators and implicit merging by guessed IDs. Large collections can get
a later explicit keyed operation; do not add one ad hoc.
Body replacement is explicit and separate. Metadata-only update preserves
all bytes after the closing frontmatter separator under the codec policy.
Expected hash covers the whole original file, including body and comments.

Preserve existing unpatched extension keys wherever the storage schema permits
them. The public operation input remains closed; creating arbitrary new
extension keys is unsupported until explicitly exposed by a descriptor.
Invalid or duplicate-key legacy metadata is never silently repaired.
Immutable identity fields cannot be renamed by an update.

No-op returns changed=false with previous_sha256=result_sha256. It does not
invent a lifecycle transition, timestamp edit, execution or evidence outcome.

## Metadata and field ownership

Registry resolves schema identity ($id + bytes SHA256 + applicable parent
schema version) from installed, verified assets and product pin.
Do not reuse global default_registry as a silent unpinned authority source.
Worker never selects arbitrary local/remote schemas. No remote reference fetch.

Some schema properties are annotations or open objects. Operation schemas
project known semantic fields and add explicit types/format assertions for the
operation contract. Storage schema corrections are separately reviewed,
versioned/synchronized changes; never silently close existing extension points.

Core supplies initial statuses through creation factories only. Missing title,
claims, spec refs, decision content or task kind is a user error, not a guessed
default. IDs remain caller-selected and validated; no allocator in MVP.
Do not add timestamp or schema_version to artifacts whose schema has no such
field. Contract-required time is captured once at prepare; retry reuses it.

Example generic update with status=verified rejects with code
core_owned_field and a hint to the existing deltafuse state command.
Writer success does not mean state transition, gate pass or verified evidence.

## Authorization and reference validation

Use current selected work item and operation-specific Core policy. Check target
kind/ownership, stage/pass, read and write authority, and all protected nested
fields. Bind a Core-generated authorization context to Change identity,
envelope, schema/lock hashes and relevant source/snapshot before commit.
Clients cannot create this context through JSON.

Core-owned commands invoke internal persistence after their own existing
authorization, transition and Human Gate logic. A Core command's valid operation
can differ from the currently offered Worker write envelope; do not disable
legitimate evidence/decide/state merely by applying the wrong actor's policy.
Expose no public actor=core parameter to bypass checks.

Classify references by contract:
- existing identity/spec/evidence dependency: validate containment, existence
  and expected identity/hash now;
- declared added/removed spec path: validate the stage-specific intent, not
  an inappropriate already-applied-state requirement;
- whole-Change convergence: separate Core gate, explicitly not evaluated by
  a single write.
For MVP create prerequisite artifacts first; no unconstrained dangling refs.
No "semantic_valid=true" for arbitrary prose. Return validation scopes.

## Canonical codec and legacy content

Strict bounded YAML reader rejects duplicate mappings, ambiguous merges,
custom tags and cyclic/alias constructs unsupported by v1. It must not turn a
malformed artifact into a valid one by dropping content.
Define scalar types carefully for quoted/unquoted dates, true/false, yes/no,
null, leading zeroes and float spellings. JSON semantic round-trip equality
is explicit; don't let library implicit coercion change a supplied string.
Use authoritative key order + deterministic ordering for allowed extension
keys, preserve list order, Unicode and multiline string content.

Canonical new metadata uses UTF-8/LF; emitted byte sequence deterministic under
same semantic payload, serializer revision and Core-supplied context.
Semantically equal inputs with reordered object keys yield same output.
Receipts may include a transaction time while unchanged artifact bytes do not.

Legacy update policy: canonicalize old mapping to detect metadata format loss.
If old raw metadata differs, return format_change_required with preview hash
and explanation; explicit canonicalize_metadata=true authorizes that metadata
rewrite for this exact expected file hash only. Preserve opaque body bytes.
Do not silently drop comments. Read-only validate and manually maintained
artifact workflows remain available. Define BOM/CRLF policy in tests:
existing body retained as bytes; canonical metadata LF; unsupported encoding
fails before write. No repository-wide migration.

## Persistence / concurrency / recovery

1. Strictly parse bounded request; resolve kind and Core access context.
2. Acquire shared product mutation lock; read expected target and relevant
   authorization/source inputs; reject stale hashes without changing files.
3. Apply field-safe patch or complete creation factory. Validate candidate
   storage schema and operation-specific Core invariants/references.
4. Serialize into same-filesystem staging, parse/revalidate and compare exact
   semantic values; fsync staging as supported. No live artifact changed yet.
5. Record durable prepared transaction with request/payload/schema/authority/
   before/after hashes. Revalidate live authority/target before publication.
6. Atomically publish: no-replace create, replacement update, never truncate
   existing target. Record publication state. Keep snapshot/receipt protocol
   coherent with existing transition journal semantics.
7. Re-read and verify resulting bytes/schema while lock held. Finalize a
   durable receipt and committed transaction; return success only now.

Single-file content atomicity is not multi-file transaction atomicity.
A recovery journal defines prepared/published/committed and uncertain outcomes.
After crash, compare exact known before/after hashes and request identity:
finish known transaction, preserve old file, or stop on ambiguity; never
guess or overwrite a third-party edit. Receipt failure after publication
returns a recoverable committed-but-unreceipted/unknown outcome, not false
unchanged or success. Never roll back over an unrelated newer file.

One request_id retried with same request hash returns the durable prior result;
same ID with different payload rejects. Recovery and retries never rerun an
evidence command or auto-accept a Human Gate. Execution ID is distinct from
persistence request ID.

All cooperating Core mutation paths share the lock. Raw-editor writes are
outside the portable advisory-lock guarantee; document/detect their drift.
Host-enforced write restriction is required for hostile-writer exclusion.
No filesystem magic is claimed. Real Windows and POSIX crash/race tests are
release requirements. Reject symlink/reparse traversal; guard Windows case,
alternate streams, device names and path identity on the actual filesystem.

Core-controlled journal/scratch paths are not made Worker-writable by adding
broad envelope exceptions. Define lock recovery/liveness and fsync guarantees
per platform. Never delete locks/temps solely by age while owner may be active.

## Receipt and diagnostics

Receipt: operation/request/transaction ID, kind, relative target, operation
schema version/hash, storage schema identity/hash/version context, serializer
revision, raw-request hash and normalized-payload hash, previous/result byte
hashes, generated fields with provenance, bound Core source/lock/authority
identities, validation scopes/results, changed flag and durable outcome.
Hash receipt excluding its own digest. Never inject receipt fields into the
artifact storage schema. Durable receipt/root must be Core-managed, not a
Worker-supplied path. An integrity digest is not independent authentication.

Error: code, JSON Pointer path, stage (input/schema/policy/reference/concurrency/
serialization/persistence/readback), concise message, optional existing value/
expected type and actionable hint. Bound response size, preserve deterministic
ordering and offer full diagnostics by reference. Do not suggest invented
semantic content or echo secrets/raw giant payloads.

Read-only validate opens no mutation transaction and changes no artifact,
receipt or journal. It distinguishes syntax/schema/identity/reference/Core
checks and not-evaluated checks. Describing operation schema has no side effects.

Proposed CLI exits: 0 successful operation/valid requested checks; 2 invalid
input/schema/reference; 3 authorization/Core-owned operation denied;
4 stale target/identity conflict; 5 persistence/recovery/indeterminate failure.
A read-only valid result means the reported scopes only, not full convergence.

## Core integration order

- Typed artifacts first; no change to legal Process transitions.
- Evidence persistence internal; extend evidence --phase verification with
  task=null and fixed run.yaml, actual authorized full-suite execution and
  measured baseline. Preserve current Red/Green/regression behavior.
- state/advance/decide share validated persistence/recovery while remaining the
  only authority for their status writes. Test old receipt replay compatibility.
- new scaffolding must meet its declared bootstrap/full-artifact contract.
  Require missing semantic inputs or explicitly retain a labelled incomplete
  scaffold; no claim that invalid scaffold is fully schema-valid.
- coverage derives before serializing; artifact.update cannot forge coverage.
- No automatic parent-index side effects during public single-file create.
  Use an explicit second Change-index update after the child exists: the
  caller supplies IDs/paths and Core resolves mirrored statuses from the real
  child artifacts. The two operations are not advertised as atomic together;
  existing gates detect missing indexing. No invented public status setter.
